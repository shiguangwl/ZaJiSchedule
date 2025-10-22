"""CPU调度模块."""

import asyncio
from datetime import UTC, datetime
from typing import Literal

from config.database import get_db
from config.settings import get_settings
from core.monitor import MonitoringData, SystemMonitor
from core.quota_manager import QuotaManager
from core.sliding_window import PeakWindow, SlidingWindow
from utils.cgroup_manager import CGroupManager
from utils.logger import get_logger

logger = get_logger(__name__)


class CPUScheduler:
    """CPU调度器.

    核心调度逻辑:
    1. 接收监控数据
    2. 更新滑动窗口
    3. 计算可用配额
    4. 动态调整CPU限制
    """

    def __init__(self) -> None:
        """初始化调度器."""
        self.settings = get_settings()
        self.db = get_db()

        # 初始化组件
        self.monitor = SystemMonitor()
        self.sliding_window = SlidingWindow(
            window_hours=self.settings.limits_avg_window_hours,
        )
        self.peak_window = PeakWindow(
            window_hours=self.settings.limits_peak_window_hours,
            peak_threshold=self.settings.limits_peak_threshold,
        )
        self.quota_manager = QuotaManager()
        self.cgroup_manager = CGroupManager()

        # 当前CPU限制
        self._current_cpu_limit: float = self.settings.limits_absolute_max_cpu
        self._last_adjustment_time: datetime | None = None

        # 运行状态
        self._running = False
        self._task: asyncio.Task | None = None

        logger.info("初始化CPU调度器")

    async def start(self) -> None:
        """启动调度器."""
        if self._running:
            logger.warning("调度器已在运行")
            return

        self._running = True

        # 初始化cgroup
        if self.settings.cgroup_enabled:
            if not self.cgroup_manager.initialize():
                logger.error("cgroup初始化失败,调度器将无法控制CPU")
            else:
                # 将当前进程添加到cgroup
                self.cgroup_manager.add_current_process()

        # 启动调度循环
        self._task = asyncio.create_task(self._schedule_loop())
        logger.info("调度器已启动")

    async def stop(self) -> None:
        """停止调度器."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("调度器已停止")

    async def _schedule_loop(self) -> None:
        """调度循环."""
        logger.info("开始调度循环")

        while self._running:
            try:
                # 采集监控数据
                monitoring_data = await self.monitor.collect_metrics()

                # 更新滑动窗口
                self.sliding_window.add_data_point(
                    monitoring_data.cpu_usage,
                    monitoring_data.timestamp,
                )
                self.peak_window.update(
                    monitoring_data.cpu_usage,
                    monitoring_data.timestamp,
                )

                # 计算可用配额
                available_quota = await self._calculate_available_quota()

                # 调整CPU限制
                new_limit = self._calculate_cpu_limit(available_quota)
                await self._adjust_cpu_limit(new_limit, monitoring_data, available_quota)

                # 保存监控数据
                await self._save_monitoring_data(monitoring_data)

                # 等待下一个周期
                await asyncio.sleep(self.settings.monitoring_interval)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("调度循环出错")
                await asyncio.sleep(self.settings.monitoring_interval)

        logger.info("调度循环结束")

    async def _calculate_available_quota(self) -> dict[str, float]:
        """计算可用配额.

        Returns:
            配额信息字典
        """
        # 12小时平均配额
        avg_12h = self.sliding_window.get_average()
        avg_quota_remaining = self.sliding_window.get_remaining_quota(
            self.settings.limits_avg_max_usage,
        )

        # 24小时峰值配额
        peak_24h = self.peak_window.get_total_peak_duration()
        peak_quota_remaining = self.peak_window.get_remaining_quota(
            self.settings.limits_peak_max_duration,
        )

        # 检查预留
        reservation = await self.quota_manager.get_active_reservation()
        reservation_quota = reservation.cpu_quota if reservation else None

        # 计算最终可用配额
        # 取所有约束的最小值
        available = self.settings.limits_avg_max_usage
        if reservation_quota is not None:
            available = min(available, reservation_quota)

        return {
            "avg_12h": avg_12h,
            "avg_quota_remaining": avg_quota_remaining,
            "peak_24h": peak_24h,
            "peak_quota_remaining": peak_quota_remaining,
            "reservation_quota": reservation_quota,
            "available_quota": available,
            "reservation_id": reservation.id if reservation else None,
        }

    def _calculate_cpu_limit(self, quota_info: dict[str, float]) -> float:
        """根据配额计算CPU限制.

        Args:
            quota_info: 配额信息

        Returns:
            建议的CPU限制(%)
        """
        avg_quota_remaining = quota_info["avg_quota_remaining"]
        peak_quota_remaining = quota_info["peak_quota_remaining"]
        reservation_quota = quota_info.get("reservation_quota")

        # 如果有预留,优先使用预留配额
        if reservation_quota is not None:
            return float(
                min(
                    reservation_quota,
                    self.settings.limits_absolute_max_cpu,
                ),
            )

        # 根据剩余配额确定CPU限制
        # 配额充足 (> 20%)
        if avg_quota_remaining > 20.0:
            target_limit = self.settings.scheduler_quota_high_cpu_limit
        # 配额紧张 (5-20%)
        elif avg_quota_remaining > 5.0:
            target_limit = self.settings.scheduler_quota_medium_cpu_limit
        # 配额即将耗尽 (< 5%)
        elif avg_quota_remaining > self.settings.scheduler_emergency_threshold:
            target_limit = self.settings.scheduler_quota_low_cpu_limit
        # 紧急模式 (< 1%)
        else:
            target_limit = self.settings.scheduler_emergency_cpu_limit

        # 考虑峰值配额
        if peak_quota_remaining < self.settings.limits_peak_critical_threshold:
            # 峰值配额紧张,进一步降低限制
            target_limit = min(target_limit, self.settings.scheduler_emergency_cpu_limit)

        # 应用安全边界
        return float(
            max(
                self.settings.limits_absolute_min_cpu,
                min(target_limit, self.settings.limits_absolute_max_cpu),
            ),
        )

    async def _adjust_cpu_limit(
        self,
        new_limit: float,
        _monitoring_data: MonitoringData,
        quota_info: dict[str, float],
    ) -> None:
        """调整CPU限制.

        Args:
            new_limit: 新的CPU限制
            monitoring_data: 监控数据
            quota_info: 配额信息
        """
        # 检查是否需要调整
        change = abs(new_limit - self._current_cpu_limit)
        if change < self.settings.scheduler_change_threshold:
            return

        # 检查调整间隔
        current_time = datetime.now(UTC)
        if self._last_adjustment_time is not None:
            elapsed = (current_time - self._last_adjustment_time).total_seconds()
            if elapsed < self.settings.scheduler_adjustment_interval:
                return

        # 平滑调整
        smoothed_limit = (
            self._current_cpu_limit * (1 - self.settings.scheduler_smooth_factor)
            + new_limit * self.settings.scheduler_smooth_factor
        )

        # 应用新限制
        if self.settings.cgroup_enabled:
            if self.cgroup_manager.set_cpu_limit(smoothed_limit):
                action: Literal["increase", "decrease", "maintain"]
                if smoothed_limit > self._current_cpu_limit:
                    action = "increase"
                elif smoothed_limit < self._current_cpu_limit:
                    action = "decrease"
                else:
                    action = "maintain"

                self._current_cpu_limit = smoothed_limit
                self._last_adjustment_time = current_time

                # 记录调度日志
                await self._log_schedule_action(
                    smoothed_limit,
                    quota_info,
                    action,
                    f"配额剩余: {quota_info['avg_quota_remaining']:.1f}%",
                )

                logger.info(
                    "调整CPU限制: %.1f%% -> %.1f%% (目标: %.1f%%)",
                    self._current_cpu_limit,
                    smoothed_limit,
                    new_limit,
                )

    async def _save_monitoring_data(self, data: MonitoringData) -> None:
        """保存监控数据到数据库.

        Args:
            data: 监控数据
        """
        try:
            is_peak = data.cpu_usage >= self.settings.limits_peak_threshold
            async with self.db.get_async_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO monitoring_data
                    (timestamp, cpu_usage, memory_usage, disk_io_read, disk_io_write,
                     network_in, network_out, cpu_limit, is_peak)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data.timestamp.isoformat(),
                        data.cpu_usage,
                        data.memory_usage,
                        data.disk_io_read,
                        data.disk_io_write,
                        data.network_in,
                        data.network_out,
                        self._current_cpu_limit,
                        is_peak,
                    ),
                )
                await conn.commit()

        except Exception:
            logger.exception("保存监控数据失败")

    async def _log_schedule_action(
        self,
        cpu_limit: float,
        quota_info: dict[str, float],
        action: str,
        reason: str,
    ) -> None:
        """记录调度动作.

        Args:
            cpu_limit: CPU限制
            quota_info: 配额信息
            action: 动作类型
            reason: 原因
        """
        try:
            async with self.db.get_async_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO schedule_logs
                    (cpu_limit, avg_12h, avg_quota_remaining, peak_24h,
                     peak_quota_remaining, available_quota, reservation_id,
                     action, reason, scheduler_mode)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cpu_limit,
                        quota_info["avg_12h"],
                        quota_info["avg_quota_remaining"],
                        quota_info["peak_24h"],
                        quota_info["peak_quota_remaining"],
                        quota_info["available_quota"],
                        quota_info.get("reservation_id"),
                        action,
                        reason,
                        self.settings.scheduler_mode,
                    ),
                )
                await conn.commit()

        except Exception:
            logger.exception("记录调度日志失败")

    def get_status(self) -> dict[str, bool | float | int]:
        """获取调度器状态.

        Returns:
            状态信息
        """
        return {
            "running": self._running,
            "current_cpu_limit": self._current_cpu_limit,
            "avg_12h": self.sliding_window.get_average(),
            "peak_24h": self.peak_window.get_total_peak_duration(),
            "data_points": self.sliding_window.get_data_count(),
            "peak_count": self.peak_window.get_peak_count(),
        }
