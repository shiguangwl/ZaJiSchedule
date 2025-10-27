"""
CPU 智能调度引擎 - 滑动窗口版本
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any

from config import ConfigManager
from database import Database

logger = logging.getLogger(__name__)


class CPUScheduler:
    """CPU 智能调度引擎 - 使用滑动窗口"""

    def __init__(self, db: Database, config: ConfigManager):
        self.db = db
        self.config = config
        self._safe_limit_cache: float | None = None
        self._cache_timestamp: float | None = None

    def _get_current_window_bounds(self) -> tuple[datetime, datetime]:
        """
        获取当前滑动窗口的开始和结束时间
        
        滑动窗口逻辑：
        1. 从当前时间往后推一个步长（滑动间隔）
        2. 以该时间点为基准，向前取一个完整窗口长度的数据

        Returns:
            (window_start, window_end)
        """
        now = datetime.now()
        window_hours = self.config.rolling_window_hours
        step_seconds = self.config.sliding_window_step_seconds
        
        # 计算滑动后的基准时间点（当前时间 + 步长）
        base_time = now + timedelta(seconds=step_seconds)
        
        # 以基准时间点向前取一个完整窗口长度
        window_end = base_time
        window_start = base_time - timedelta(hours=window_hours)

        return window_start, window_end

    def calculate_sliding_window_avg(self) -> tuple[float, int]:
        """
        计算当前滑动窗口内的平均 CPU 使用率
        
        应用最低负载保障机制：
        - 对于窗口内的每个数据点，如果实际值小于配置的最低负载值，则取最低负载值
        - 计算公式: 有效值 = max(实际数据点值, 最低负载配置值)
        - 使用处理后的有效值来计算窗口平均值

        Returns:
            (平均 CPU 使用率, 数据点数量)
        """
        window_start, window_end = self._get_current_window_bounds()

        # 获取窗口内的所有数据
        metrics = self.db.get_metrics_since(window_start.isoformat())

        # 过滤出窗口范围内的数据
        window_metrics = [m for m in metrics if window_start <= datetime.fromisoformat(m["timestamp"]) < window_end]

        if not window_metrics:
            return 0.0, 0

        # 应用最低负载保障机制
        min_load = self.config.min_load_percent
        effective_values = []
        
        for m in window_metrics:
            # 有效值 = max(实际数据点值, 最低负载配置值)
            effective_value = max(m["cpu_percent"], min_load)
            effective_values.append(effective_value)

        # 使用处理后的有效值计算平均值
        avg_cpu = sum(effective_values) / len(effective_values)

        return round(avg_cpu, 2), len(window_metrics)

    def calculate_safe_cpu_limit(self) -> float:
        """
        计算安全的 CPU 限制（滑动窗口算法）

        核心逻辑：
        1. 获取当前滑动窗口的开始和结束时间
        2. 基于滑动窗口内的数据点计算平均值（应用最低负载保障机制）
        3. 根据平均值动态计算当前可用的 CPU 占比
        4. 计算剩余时间和剩余配额
        5. 预留剩余时间的最低负载配额
        6. 剩余配额动态分配
        7. safe_limit = min_load + 动态部分

        Returns:
            安全的 CPU 限制百分比
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
        avg_limit = self.config.avg_load_limit_percent
        safety_factor = self.config.safety_factor

        # 获取当前滑动窗口的开始和结束时间
        window_start, window_end = self._get_current_window_bounds()
        now = datetime.now()

        # 计算窗口总时长（分钟）
        window_total_minutes = (window_end - window_start).total_seconds() / 60

        # 计算已用时间（分钟）- 基于滑动窗口
        elapsed_minutes = (now - window_start).total_seconds() / 60

        # 计算剩余时间（分钟）- 基于滑动窗口
        remaining_minutes = max(0, (window_end - now).total_seconds() / 60)

        # 使用滑动窗口计算平均CPU（应用最低负载保障机制）
        avg_cpu, data_points = self.calculate_sliding_window_avg()

        # 计算总配额和已用配额
        total_quota = avg_limit * window_total_minutes
        used_quota = avg_cpu * elapsed_minutes
        remaining_quota = total_quota - used_quota

        logger.info(
            f"[滑动窗口] 窗口: {window_start.strftime('%H:%M')}-{window_end.strftime('%H:%M')}, "
            f"已用时间: {elapsed_minutes:.1f}min, 剩余时间: {remaining_minutes:.1f}min, "
            f"平均CPU: {avg_cpu:.2f}% (含最低负载保障), 数据点: {data_points}, 剩余配额: {remaining_quota:.2f}%·min",
        )

        # 如果剩余时间很少（< 1分钟），使用最低负载
        if remaining_minutes < 1.0:
            safe_limit = min_load
            logger.info(f"[滑动窗口] 窗口即将结束，使用最低负载: {safe_limit:.2f}%")
        else:
            # 计算未来需要的最低负载配额
            future_min_quota = min_load * remaining_minutes

            if remaining_quota <= 0:
                # 剩余配额耗尽，只能使用最低负载
                safe_limit = min_load
                logger.error(
                    f"[滑动窗口] ⚠️ 配额管理失败！剩余配额耗尽: {remaining_quota:.2f}%·min <= 0, "
                    f"但仍使用最低负载 {min_load}% 以保证系统运行，预计将超限！",
                )
            elif remaining_quota < future_min_quota:
                # 剩余配额不足以支持最低负载，只能使用最低负载
                theoretical_limit = (remaining_quota / remaining_minutes) * safety_factor
                safe_limit = min_load
                logger.error(
                    f"[滑动窗口] ⚠️ 配额管理失败！剩余配额不足: {remaining_quota:.2f}%·min < "
                    f"future_min_quota={future_min_quota:.2f}%·min, "
                    f"理论限制={theoretical_limit:.2f}% < min_load {min_load}%, "
                    f"但仍使用最低负载 {min_load}% 以保证系统运行，预计将超限！",
                )
            else:
                # 剩余配额充足，可以分配动态部分
                dynamic_quota = remaining_quota - future_min_quota
                dynamic_limit = (dynamic_quota / remaining_minutes) * safety_factor

                # 检查时间段配置，从动态部分中扣除预留
                time_slot_reserved = self._calculate_time_slot_reservation()
                dynamic_limit = max(0, dynamic_limit - time_slot_reserved)

                # 最终限制 = 最低负载 + 动态部分
                safe_limit = min_load + dynamic_limit

                logger.info(
                    f"[滑动窗口] 配额充足: remaining_quota={remaining_quota:.2f}%·min, "
                    f"future_min_quota={future_min_quota:.2f}%·min, "
                    f"dynamic_quota={dynamic_quota:.2f}%·min, "
                    f"dynamic_limit={dynamic_limit:.2f}%, "
                    f"time_slot_reserved={time_slot_reserved:.2f}%, "
                    f"safe_limit={safe_limit:.2f}%",
                )

        # 限制在 [min_load, max_load] 范围内
        safe_limit = max(min_load, min(max_load, safe_limit))

        logger.info(f"[滑动窗口] 最终限制: {safe_limit:.2f}%")

        # 更新缓存
        self._safe_limit_cache = safe_limit
        self._cache_timestamp = current_time

        return safe_limit

    def _calculate_time_slot_reservation(self) -> float:
        """
        计算当前时间段的预留配额

        Returns:
            需要预留的 CPU 百分比
        """
        time_slots = self.db.get_time_slots()
        if not time_slots:
            return 0.0

        now = datetime.now()
        current_time = now.strftime("%H:%M")

        for slot in time_slots:
            if not slot["enabled"]:
                continue

            start_time = slot["start_time"]
            end_time = slot["end_time"]

            # 检查当前时间是否在时间段内
            if start_time <= current_time < end_time:
                max_load = self.config.max_load_percent
                slot_max = slot["max_load_percent"]

                # 如果时间段限制低于系统最大负载，需要预留差值
                if slot_max < max_load:
                    reserved = max_load - slot_max
                    logger.info(
                        f"时间段限制生效: {start_time}-{end_time}, "
                        f"max_load={max_load}%, slot_max={slot_max}%, "
                        f"reserved={reserved}%",
                    )
                    return reserved

        return 0.0

    def get_status(self) -> dict[str, Any]:
        """
        获取调度器状态信息

        Returns:
            包含调度器状态的字典
        """
        window_start, window_end = self._get_current_window_bounds()
        avg_cpu, data_points = self.calculate_sliding_window_avg()
        safe_limit = self.calculate_safe_cpu_limit()

        now = datetime.now()
        elapsed_minutes = (now - window_start).total_seconds() / 60
        remaining_minutes = (window_end - now).total_seconds() / 60
        window_total_minutes = (window_end - window_start).total_seconds() / 60

        total_quota = self.config.avg_load_limit_percent * window_total_minutes
        used_quota = avg_cpu * elapsed_minutes
        remaining_quota = total_quota - used_quota

        return {
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "elapsed_minutes": round(elapsed_minutes, 2),
            "remaining_minutes": round(remaining_minutes, 2),
            "avg_cpu_percent": avg_cpu,
            "data_points": data_points,
            "safe_limit_percent": round(safe_limit, 2),
            "total_quota": round(total_quota, 2),
            "used_quota": round(used_quota, 2),
            "remaining_quota": round(remaining_quota, 2),
        }

    def get_scheduler_status(self) -> dict[str, Any]:
        """
        获取调度器状态（兼容旧接口）

        Returns:
            包含调度器状态的字典，格式兼容 main.py 的调用
        """
        # 获取当前 CPU 使用率
        metrics_list = self.db.get_latest_metrics(limit=1)
        current_cpu = metrics_list[0].get("cpu_percent", 0.0) if metrics_list else 0.0

        # 获取滑动窗口平均 CPU
        avg_cpu, data_points = self.calculate_sliding_window_avg()

        # 获取安全限制
        safe_limit = self.calculate_safe_cpu_limit()

        # 获取窗口信息
        window_start, window_end = self._get_current_window_bounds()
        now = datetime.now()
        elapsed_minutes = (now - window_start).total_seconds() / 60
        remaining_minutes = (window_end - now).total_seconds() / 60
        window_total_minutes = (window_end - window_start).total_seconds() / 60

        # 计算配额信息
        avg_load_limit = self.config.avg_load_limit_percent
        total_quota = avg_load_limit * window_total_minutes
        used_quota = avg_cpu * elapsed_minutes
        remaining_quota = total_quota - used_quota

        # 计算建议CPU使用率(未来时间内应保持的CPU使用率)
        if remaining_minutes > 0:
            target_cpu_percent = remaining_quota / remaining_minutes
        else:
            target_cpu_percent = self.config.min_load_percent

        # 计算距离限制(当前滑动窗口平均CPU与目标限制的差值)
        margin_absolute = avg_load_limit - avg_cpu

        # 计算风险等级
        quota_usage_percent = (used_quota / total_quota * 100) if total_quota > 0 else 0
        if quota_usage_percent >= 90:
            risk_level = "high"
        elif quota_usage_percent >= 70:
            risk_level = "medium"
        else:
            risk_level = "low"

        # 判断是否为启动初期(数据点数量不足)
        window_hours = self.config.rolling_window_hours
        expected_data_points = window_hours * 3600 / self.config.metrics_interval_seconds
        startup_threshold = expected_data_points * 0.1  # 固定10%阈值
        is_startup_period = data_points < startup_threshold

        status = {
            "safe_cpu_limit": round(safe_limit, 2),
            "current_cpu_percent": round(current_cpu, 2),
            "sliding_window_avg_cpu": round(avg_cpu, 2),
            "avg_load_limit": round(avg_load_limit, 2),
            "margin_absolute": round(margin_absolute, 2),
            "data_points": data_points,
            "risk_level": risk_level,
            "is_startup_period": is_startup_period,
            "config": {
                "window_hours": window_hours,
                "sliding_window_step_seconds": self.config.sliding_window_step_seconds,
                "min_load_percent": self.config.min_load_percent,
                "max_load_percent": self.config.max_load_percent,
                "safety_factor": self.config.safety_factor,
            },
            "quota_info": {
                "total_quota": round(total_quota, 2),
                "used_quota": round(used_quota, 2),
                "remaining_quota": round(remaining_quota, 2),
                "quota_usage_percent": round(quota_usage_percent, 2),
                "target_cpu_percent": round(target_cpu_percent, 2),
                "elapsed_minutes": round(elapsed_minutes, 2),
                "remaining_minutes": round(remaining_minutes, 2),
                "actual_minutes": round(elapsed_minutes, 2),
                "window_minutes": round(window_total_minutes, 2),
            },
        }
        status["sliding_window_avg_cpu"] = status.get(
            "avg_cpu_percent", status.get("sliding_window_avg_cpu")
        )
        return status
