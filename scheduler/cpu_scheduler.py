"""
CPU 智能调度引擎
"""
from typing import Dict, Any, Tuple
from datetime import datetime, timedelta
from database import Database
from config import ConfigManager
import logging

logger = logging.getLogger(__name__)


class CPUScheduler:
    """CPU 智能调度引擎"""

    def __init__(self, db: Database, config: ConfigManager):
        self.db = db
        self.config = config

    def calculate_rolling_window_avg(self) -> Tuple[float, int]:
        """
        计算滚动窗口内的平均 CPU 使用率

        Returns:
            (平均 CPU 使用率, 数据点数量)
        """
        window_hours = self.config.rolling_window_hours
        metrics = self.db.get_metrics_in_window(window_hours)

        if not metrics:
            return 0.0, 0

        total_cpu = sum(m["cpu_percent"] for m in metrics)
        avg_cpu = total_cpu / len(metrics)

        return round(avg_cpu, 2), len(metrics)

    def calculate_remaining_quota(self) -> Dict[str, float]:
        """
        计算剩余的 CPU 配额

        Returns:
            包含剩余配额信息的字典
        """
        window_hours = self.config.rolling_window_hours
        avg_limit = self.config.avg_load_limit_percent

        # 获取窗口内的数据
        metrics = self.db.get_metrics_in_window(window_hours)

        if not metrics:
            return {
                "total_quota": avg_limit * window_hours * 3600,  # 总配额(百分比*秒)
                "used_quota": 0.0,
                "remaining_quota": avg_limit * window_hours * 3600,
                "remaining_hours": window_hours,
                "avg_cpu_percent": 0.0
            }

        # 计算已使用的配额
        # 假设每个数据点代表采集间隔的平均值
        interval_seconds = self.config.metrics_interval_seconds
        used_quota = sum(m["cpu_percent"] * interval_seconds for m in metrics)

        # 总配额 = 平均限制 * 窗口时长(秒)
        total_quota = avg_limit * window_hours * 3600

        # 剩余配额
        remaining_quota = total_quota - used_quota

        # 计算窗口剩余时间
        if metrics:
            first_timestamp = datetime.fromisoformat(metrics[0]["timestamp"])
            window_end = first_timestamp + timedelta(hours=window_hours)
            remaining_seconds = (window_end - datetime.now()).total_seconds()
            remaining_hours = max(0, remaining_seconds / 3600)
        else:
            remaining_hours = window_hours

        # 当前平均 CPU 使用率
        avg_cpu = sum(m["cpu_percent"] for m in metrics) / len(metrics)

        return {
            "total_quota": round(total_quota, 2),
            "used_quota": round(used_quota, 2),
            "remaining_quota": round(remaining_quota, 2),
            "remaining_hours": round(remaining_hours, 2),
            "avg_cpu_percent": round(avg_cpu, 2)
        }

    def calculate_safe_cpu_limit(self) -> float:
        """
        计算当前安全的 CPU 使用上限

        Returns:
            建议的 CPU 使用上限(百分比)
        """
        min_load = self.config.min_load_percent
        max_load = self.config.max_load_percent

        # 获取剩余配额信息
        quota_info = self.calculate_remaining_quota()
        remaining_quota = quota_info["remaining_quota"]
        remaining_hours = quota_info["remaining_hours"]

        # 如果剩余时间很少,使用保守策略
        if remaining_hours < 0.1:
            return min_load

        # 计算基于剩余配额的安全上限
        # 安全系数 0.9,留 10% 余量
        safety_factor = 0.9
        interval_seconds = self.config.metrics_interval_seconds

        # 基于剩余配额计算的上限
        quota_based_limit = (remaining_quota * safety_factor) / (remaining_hours * 3600 / interval_seconds)

        # 检查时间段配置,预留配额
        time_slot_reserved = self._calculate_time_slot_reservation()
        quota_based_limit -= time_slot_reserved

        # 限制在 min_load 和 max_load 之间
        safe_limit = max(min_load, min(max_load, quota_based_limit))

        logger.info(f"计算安全 CPU 限制: quota_based={quota_based_limit:.2f}, "
                   f"time_slot_reserved={time_slot_reserved:.2f}, "
                   f"final={safe_limit:.2f}")

        return round(safe_limit, 2)

    def _calculate_time_slot_reservation(self) -> float:
        """
        计算时间段配置需要预留的 CPU 配额

        Returns:
            需要预留的 CPU 百分比
        """
        time_slots = self.db.get_time_slots()
        if not time_slots:
            return 0.0

        now = datetime.now()
        now.time()

        total_reservation = 0.0
        window_hours = self.config.rolling_window_hours
        window_end = now + timedelta(hours=window_hours)

        for slot in time_slots:
            if not slot["enabled"]:
                continue

            start_time = datetime.strptime(slot["start_time"], "%H:%M").time()
            end_time = datetime.strptime(slot["end_time"], "%H:%M").time()
            max_load = slot["max_load_percent"]

            # 检查时间段是否在滚动窗口内
            slot_start_today = datetime.combine(now.date(), start_time)
            slot_end_today = datetime.combine(now.date(), end_time)

            # 处理跨天的情况
            if end_time < start_time:
                slot_end_today += timedelta(days=1)

            # 如果时间段在未来且在窗口内
            if slot_start_today > now and slot_start_today < window_end:
                # 计算时间段的持续时间(小时)
                slot_duration_hours = (slot_end_today - slot_start_today).total_seconds() / 3600

                # 预留配额 = 时间段最大负载 * 持续时间
                reservation = max_load * slot_duration_hours / window_hours
                total_reservation += reservation

                logger.info(f"时间段 {slot['start_time']}-{slot['end_time']} "
                           f"需要预留 {reservation:.2f}% CPU")

        return round(total_reservation, 2)

    def get_scheduler_status(self) -> Dict[str, Any]:
        """
        获取调度器状态信息

        Returns:
            包含调度器状态的字典
        """
        avg_cpu, data_points = self.calculate_rolling_window_avg()
        quota_info = self.calculate_remaining_quota()
        safe_limit = self.calculate_safe_cpu_limit()

        # 计算距离限制的余量
        avg_limit = self.config.avg_load_limit_percent
        margin = avg_limit - avg_cpu
        margin_percent = (margin / avg_limit * 100) if avg_limit > 0 else 0

        # 风险等级评估
        if margin_percent > 30:
            risk_level = "low"
        elif margin_percent > 15:
            risk_level = "medium"
        elif margin_percent > 5:
            risk_level = "high"
        else:
            risk_level = "critical"

        return {
            "rolling_window_avg_cpu": avg_cpu,
            "avg_load_limit": avg_limit,
            "margin_percent": round(margin_percent, 2),
            "risk_level": risk_level,
            "safe_cpu_limit": safe_limit,
            "data_points": data_points,
            "quota_info": quota_info,
            "config": {
                "min_load": self.config.min_load_percent,
                "max_load": self.config.max_load_percent,
                "window_hours": self.config.rolling_window_hours,
                "avg_limit": avg_limit
            }
        }

    def should_throttle_cpu(self, current_cpu: float) -> Tuple[bool, str]:
        """
        判断是否需要限制 CPU 使用

        Args:
            current_cpu: 当前 CPU 使用率

        Returns:
            (是否需要限制, 原因说明)
        """
        safe_limit = self.calculate_safe_cpu_limit()

        if current_cpu > safe_limit:
            return True, f"当前 CPU {current_cpu}% 超过安全限制 {safe_limit}%"

        # 检查是否接近平均限制
        avg_cpu, _ = self.calculate_rolling_window_avg()
        avg_limit = self.config.avg_load_limit_percent

        if avg_cpu > avg_limit * 0.95:  # 超过 95% 的限制
            return True, f"滚动窗口平均 CPU {avg_cpu}% 接近限制 {avg_limit}%"

        return False, "CPU 使用在安全范围内"

