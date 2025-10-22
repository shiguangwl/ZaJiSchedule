"""滑动窗口算法实现."""

from collections import deque
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from utils.logger import get_logger

logger = get_logger(__name__)


class PeakPeriod(NamedTuple):
    """峰值使用时段."""

    start_time: datetime
    duration: float  # 秒


class SlidingWindow:
    """12小时平均使用率滑动窗口.

    使用循环队列存储过去12小时的CPU使用率数据点,
    维护累计和以O(1)时间复杂度计算平均值.
    """

    def __init__(self, window_hours: int = 12) -> None:
        """初始化滑动窗口.

        Args:
            window_hours: 窗口长度(小时)
        """
        self.window_hours = window_hours
        self.window_seconds = window_hours * 3600
        self.max_data_points = self.window_seconds  # 每秒一个数据点

        # 使用deque作为循环队列
        self.data_points: deque[tuple[datetime, float]] = deque(
            maxlen=self.max_data_points,
        )
        self.sum_usage = 0.0  # 累计和

        logger.info(
            "初始化滑动窗口: window_hours=%d, max_data_points=%d",
            window_hours,
            self.max_data_points,
        )

    def add_data_point(self, cpu_usage: float, timestamp: datetime | None = None) -> None:
        """添加新的CPU使用率数据点.

        Args:
            cpu_usage: CPU使用率(0-100)
            timestamp: 时间戳,默认为当前时间
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)

        # 如果队列已满,移除最旧的数据点
        if len(self.data_points) >= self.max_data_points:
            _, old_usage = self.data_points[0]
            self.sum_usage -= old_usage

        # 添加新数据点
        self.data_points.append((timestamp, cpu_usage))
        self.sum_usage += cpu_usage

    def get_average(self) -> float:
        """获取当前平均CPU使用率.

        Returns:
            平均CPU使用率(0-100)
        """
        if not self.data_points:
            return 0.0
        return self.sum_usage / len(self.data_points)

    def get_remaining_quota(self, max_usage: float) -> float:
        """获取剩余配额.

        Args:
            max_usage: 最大允许的平均使用率(%)

        Returns:
            剩余配额(%)
        """
        current_avg = self.get_average()
        return max(0.0, max_usage - current_avg)

    def get_data_count(self) -> int:
        """获取当前数据点数量."""
        return len(self.data_points)

    def is_full(self) -> bool:
        """检查窗口是否已满."""
        return len(self.data_points) >= self.max_data_points

    def clear(self) -> None:
        """清空窗口数据."""
        self.data_points.clear()
        self.sum_usage = 0.0
        logger.info("清空滑动窗口数据")


class PeakWindow:
    """24小时峰值使用窗口.

    追踪过去24小时内CPU峰值使用(>95%)的总时长.
    """

    def __init__(
        self,
        window_hours: int = 24,
        peak_threshold: float = 95.0,
    ) -> None:
        """初始化峰值窗口.

        Args:
            window_hours: 窗口长度(小时)
            peak_threshold: 峰值阈值(%)
        """
        self.window_hours = window_hours
        self.window_seconds = window_hours * 3600
        self.peak_threshold = peak_threshold

        # 存储峰值时段
        self.peak_periods: deque[PeakPeriod] = deque()

        # 当前峰值时段
        self.current_peak_start: datetime | None = None

        logger.info(
            "初始化峰值窗口: window_hours=%d, peak_threshold=%.1f",
            window_hours,
            peak_threshold,
        )

    def update(self, cpu_usage: float, timestamp: datetime | None = None) -> None:
        """更新峰值使用状态.

        Args:
            cpu_usage: CPU使用率(0-100)
            timestamp: 时间戳,默认为当前时间
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)

        is_peak = cpu_usage >= self.peak_threshold

        if is_peak:
            # 进入峰值状态
            if self.current_peak_start is None:
                self.current_peak_start = timestamp
                logger.debug("开始峰值使用: timestamp=%s", timestamp)
        # 退出峰值状态
        elif self.current_peak_start is not None:
            duration = (timestamp - self.current_peak_start).total_seconds()
            self.peak_periods.append(
                PeakPeriod(start_time=self.current_peak_start, duration=duration),
            )
            logger.debug(
                "结束峰值使用: start=%s, duration=%.1fs",
                self.current_peak_start,
                duration,
            )
            self.current_peak_start = None

        # 清理过期数据
        self._cleanup_old_periods(timestamp)

    def _cleanup_old_periods(self, current_time: datetime) -> None:
        """清理超过窗口时间的峰值时段.

        Args:
            current_time: 当前时间
        """
        cutoff_time = current_time - timedelta(seconds=self.window_seconds)
        while self.peak_periods and self.peak_periods[0].start_time < cutoff_time:
            removed = self.peak_periods.popleft()
            logger.debug("清理过期峰值时段: start=%s", removed.start_time)

    def get_total_peak_duration(self) -> float:
        """获取峰值使用总时长.

        Returns:
            峰值使用总时长(秒)
        """
        total = sum(period.duration for period in self.peak_periods)

        # 如果当前正在峰值状态,加上当前峰值时长
        if self.current_peak_start is not None:
            current_duration = (datetime.now(UTC) - self.current_peak_start).total_seconds()
            total += current_duration

        return total

    def get_remaining_quota(self, max_duration: float) -> float:
        """获取剩余峰值配额.

        Args:
            max_duration: 最大允许的峰值时长(秒)

        Returns:
            剩余峰值配额(秒)
        """
        current_total = self.get_total_peak_duration()
        return max(0.0, max_duration - current_total)

    def get_peak_count(self) -> int:
        """获取峰值时段数量."""
        count = len(self.peak_periods)
        if self.current_peak_start is not None:
            count += 1
        return count

    def clear(self) -> None:
        """清空窗口数据."""
        self.peak_periods.clear()
        self.current_peak_start = None
        logger.info("清空峰值窗口数据")
