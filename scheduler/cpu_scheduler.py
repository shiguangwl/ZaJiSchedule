"""
CPU 智能调度引擎
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any

import psutil

from config import ConfigManager
from database import Database

logger = logging.getLogger(__name__)


class CPUScheduler:
    """CPU 智能调度引擎"""

    def __init__(self, db: Database, config: ConfigManager):
        self.db = db
        self.config = config
        self._safe_limit_cache: float | None = None
        self._cache_timestamp: float | None = None

    def calculate_rolling_window_avg(self) -> tuple[float, int]:
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

    def calculate_remaining_quota(self) -> dict[str, float]:
        """
        计算剩余的 CPU 配额（基于滑动窗口）

        Returns:
            包含剩余配额信息的字典
            - total_quota: 总配额 (单位: 百分比·分钟)
            - used_quota: 已用配额 (单位: 百分比·分钟)
            - remaining_quota: 剩余配额 (单位: 百分比·分钟)
            - avg_cpu_percent: 平均 CPU 使用率
            - target_cpu_percent: 剩余时间内的目标 CPU 使用率
            - actual_minutes: 实际运行时长 (分钟)
            - window_minutes: 窗口时长 (分钟)
        """
        window_hours = self.config.rolling_window_hours
        avg_limit = self.config.avg_load_limit_percent

        # 转换为分钟
        window_minutes = window_hours * 60

        # 获取窗口内的数据（滑动窗口：now - window_hours 到 now）
        metrics = self.db.get_metrics_in_window(window_hours)

        if not metrics:
            return {
                "total_quota": avg_limit * window_minutes,  # 总配额(百分比·分钟)
                "used_quota": 0.0,
                "remaining_quota": avg_limit * window_minutes,
                "avg_cpu_percent": 0.0,
                "target_cpu_percent": avg_limit,
                "actual_minutes": 0.0,
                "window_minutes": window_minutes,
            }

        # 计算实际运行时长（从第一个数据点到现在）
        from datetime import datetime

        first_timestamp = datetime.fromisoformat(metrics[0]["timestamp"])
        now = datetime.now()
        actual_seconds = (now - first_timestamp).total_seconds()
        actual_minutes = actual_seconds / 60

        # 计算平均 CPU 使用率（实际运行期间的平均）
        avg_cpu = sum(m["cpu_percent"] for m in metrics) / len(metrics)

        # 总配额 = 平均限制 × 窗口时长 (单位: 百分比·分钟)
        total_quota = avg_limit * window_minutes

        # 已用配额 = 平均CPU × 实际运行时长 (单位: 百分比·分钟)
        # 关键修复：使用实际运行时长，而不是窗口时长
        used_quota = avg_cpu * actual_minutes

        # 剩余配额 = 总配额 - 已用配额
        remaining_quota = total_quota - used_quota

        # 剩余时间 = 窗口时长 - 实际运行时长
        remaining_minutes = max(0, window_minutes - actual_minutes)

        # 目标 CPU 使用率：未来剩余时间内应该保持的 CPU 使用率
        # 如果还有剩余时间，计算未来应该保持的CPU使用率
        if remaining_minutes > 0:
            # 未来可用配额 = 剩余配额
            # 目标CPU = 剩余配额 / 剩余时间
            target_cpu_percent = max(0, min(100, remaining_quota / remaining_minutes))
        else:
            # 如果已经运行满窗口时长，目标就是限制值
            target_cpu_percent = avg_limit if remaining_quota >= 0 else 0

        return {
            "total_quota": round(total_quota, 2),
            "used_quota": round(used_quota, 2),
            "remaining_quota": round(remaining_quota, 2),
            "avg_cpu_percent": round(avg_cpu, 2),
            "target_cpu_percent": round(target_cpu_percent, 2),
            "actual_minutes": round(actual_minutes, 2),
            "window_minutes": window_minutes,
        }

    def calculate_safe_cpu_limit(self) -> float:
        """
        计算当前安全的 CPU 使用上限（基于滑动窗口）

        Returns:
            建议的 CPU 使用上限(百分比)
        """
        current_time = time.time()

        # 检查缓存是否有效（同一秒内使用缓存）
        if (
            self._safe_limit_cache is not None
            and self._cache_timestamp is not None
            and current_time - self._cache_timestamp < 1.0
        ):
            return self._safe_limit_cache

        min_load = self.config.min_load_percent
        max_load = self.config.max_load_percent

        # 获取剩余配额信息
        quota_info = self.calculate_remaining_quota()
        remaining_quota = quota_info["remaining_quota"]  # 单位: 百分比·分钟
        target_cpu = quota_info["target_cpu_percent"]  # 目标 CPU 使用率
        avg_cpu = quota_info["avg_cpu_percent"]  # 当前平均 CPU

        # 计算基于剩余配额的安全上限
        # 从配置中获取安全系数
        safety_factor = self.config.safety_factor

        # 启动初期保护: 如果数据不足窗口时长的阈值,使用更保守的安全系数
        window_minutes = self.config.rolling_window_hours * 60
        actual_minutes = quota_info["actual_minutes"]
        threshold_percent = self.config.startup_data_threshold_percent
        if actual_minutes < window_minutes * (threshold_percent / 100):
            safety_factor = self.config.startup_safety_factor
            logger.info(
                f"启动初期保护: 数据不足({actual_minutes:.0f}min < {window_minutes * threshold_percent / 100:.0f}min), "
                f"使用启动安全系数 {safety_factor}",
            )

        # 如果剩余配额为正，使用目标CPU作为基准
        # 如果剩余配额为负，需要更保守的策略
        if remaining_quota >= 0:
            # 未超限：使用目标CPU × 安全系数
            quota_based_limit = target_cpu * safety_factor
        else:
            # 已超限：需要降低到目标CPU以下
            # 目标是让滑动窗口的平均逐渐回到限制内
            quota_based_limit = target_cpu * safety_factor

        # 检查时间段配置,预留配额
        time_slot_reserved = self._calculate_time_slot_reservation()
        quota_based_limit -= time_slot_reserved

        # 限制在 min_load 和 max_load 之间
        safe_limit = max(min_load, min(max_load, quota_based_limit))

        logger.info(
            f"计算安全 CPU 限制: avg_cpu={avg_cpu:.2f}%, "
            f"remaining_quota={remaining_quota:.2f}%·min, "
            f"target_cpu={target_cpu:.2f}%, "
            f"quota_based={quota_based_limit:.2f}%, "
            f"time_slot_reserved={time_slot_reserved:.2f}%, "
            f"final={safe_limit:.2f}%",
        )

        # 更新缓存
        self._safe_limit_cache = round(safe_limit, 2)
        self._cache_timestamp = current_time

        return self._safe_limit_cache

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

                logger.info(f"时间段 {slot['start_time']}-{slot['end_time']} 需要预留 {reservation:.2f}% CPU")

        return round(total_reservation, 2)

    def get_scheduler_status(self) -> dict[str, Any]:
        """
        获取调度器状态信息

        Returns:
            包含调度器状态的字典
        """
        avg_cpu, data_points = self.calculate_rolling_window_avg()
        quota_info = self.calculate_remaining_quota()
        safe_limit = self.calculate_safe_cpu_limit()

        # 获取当前CPU使用率
        current_cpu = psutil.cpu_percent(interval=None)

        # 计算距离限制的余量
        avg_limit = self.config.avg_load_limit_percent
        margin_absolute = avg_limit - avg_cpu  # 绝对余量 (百分比)
        margin_percent = (margin_absolute / avg_limit * 100) if avg_limit > 0 else 0  # 相对余量 (%)

        # 负载等级评估（基于相对余量）
        if margin_percent > 30:
            risk_level = "low"
        elif margin_percent > 15:
            risk_level = "medium"
        elif margin_percent > 5:
            risk_level = "high"
        else:
            risk_level = "critical"

        return {
            "current_cpu_percent": current_cpu,  # 当前瞬时CPU使用率
            "rolling_window_avg_cpu": avg_cpu,
            "avg_load_limit": avg_limit,
            "margin_absolute": round(margin_absolute, 2),  # 绝对余量 (百分比)
            "margin_percent": round(margin_percent, 2),  # 相对余量 (占限制的百分比)
            "risk_level": risk_level,
            "safe_cpu_limit": safe_limit,
            "data_points": data_points,
            "quota_info": quota_info,
            "config": {
                "min_load": self.config.min_load_percent,
                "max_load": self.config.max_load_percent,
                "window_hours": self.config.rolling_window_hours,
                "avg_limit": avg_limit,
            },
        }

    def should_throttle_cpu(self, current_cpu: float) -> tuple[bool, str]:
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
