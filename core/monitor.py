"""系统监控模块."""

import asyncio
from datetime import UTC, datetime
from typing import NamedTuple

import psutil

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


class MonitoringData(NamedTuple):
    """监控数据."""

    timestamp: datetime
    cpu_usage: float  # CPU使用率(%)
    memory_usage: float  # 内存使用率(%)
    disk_io_read: float  # 磁盘读取速率(bytes/s)
    disk_io_write: float  # 磁盘写入速率(bytes/s)
    network_in: float  # 网络接收速率(bytes/s)
    network_out: float  # 网络发送速率(bytes/s)


class SystemMonitor:
    """系统监控器.

    使用psutil采集系统指标:CPU、内存、磁盘IO、网络流量.
    """

    def __init__(self) -> None:
        """初始化系统监控器."""
        self.settings = get_settings()

        # 上一次的统计数据(用于计算增量)
        self._last_disk_io: psutil._common.sdiskio | None = None
        self._last_network_io: psutil._common.snetio | None = None
        self._last_timestamp: datetime | None = None

        logger.info("初始化系统监控器")

    async def collect_metrics(self) -> MonitoringData:
        """采集系统指标.

        Returns:
            监控数据
        """
        current_time = datetime.now(UTC)

        # CPU使用率
        cpu_usage = 0.0
        if self.settings.monitoring_enable_cpu:
            cpu_usage = await asyncio.to_thread(
                psutil.cpu_percent,
                interval=0.1,
            )

        # 内存使用率
        memory_usage = 0.0
        if self.settings.monitoring_enable_memory:
            memory = await asyncio.to_thread(psutil.virtual_memory)
            memory_usage = memory.percent

        # 磁盘IO速率
        disk_io_read = 0.0
        disk_io_write = 0.0
        if self.settings.monitoring_enable_disk:
            disk_io_read, disk_io_write = await self._get_disk_io_rate(current_time)

        # 网络流量速率
        network_in = 0.0
        network_out = 0.0
        if self.settings.monitoring_enable_network:
            network_in, network_out = await self._get_network_rate(current_time)

        return MonitoringData(
            timestamp=current_time,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_io_read=disk_io_read,
            disk_io_write=disk_io_write,
            network_in=network_in,
            network_out=network_out,
        )

    async def _get_disk_io_rate(self, current_time: datetime) -> tuple[float, float]:
        """获取磁盘IO速率.

        Args:
            current_time: 当前时间

        Returns:
            (读取速率, 写入速率) bytes/s
        """
        try:
            disk_io = await asyncio.to_thread(psutil.disk_io_counters)
            if disk_io is None:
                return 0.0, 0.0

            if self._last_disk_io is None or self._last_timestamp is None:
                self._last_disk_io = disk_io
                self._last_timestamp = current_time
                return 0.0, 0.0

            # 计算时间间隔
            time_delta = (current_time - self._last_timestamp).total_seconds()
            if time_delta <= 0:
                return 0.0, 0.0

            # 计算速率
            read_rate = (disk_io.read_bytes - self._last_disk_io.read_bytes) / time_delta
            write_rate = (disk_io.write_bytes - self._last_disk_io.write_bytes) / time_delta

            self._last_disk_io = disk_io
            self._last_timestamp = current_time

            return max(0.0, read_rate), max(0.0, write_rate)

        except Exception:
            logger.exception("获取磁盘IO速率失败")
            return 0.0, 0.0

    async def _get_network_rate(self, current_time: datetime) -> tuple[float, float]:
        """获取网络流量速率.

        Args:
            current_time: 当前时间

        Returns:
            (接收速率, 发送速率) bytes/s
        """
        try:
            network_io = await asyncio.to_thread(psutil.net_io_counters)
            if network_io is None:
                return 0.0, 0.0

            if self._last_network_io is None or self._last_timestamp is None:
                self._last_network_io = network_io
                self._last_timestamp = current_time
                return 0.0, 0.0

            # 计算时间间隔
            time_delta = (current_time - self._last_timestamp).total_seconds()
            if time_delta <= 0:
                return 0.0, 0.0

            # 计算速率
            recv_rate = (network_io.bytes_recv - self._last_network_io.bytes_recv) / time_delta
            sent_rate = (network_io.bytes_sent - self._last_network_io.bytes_sent) / time_delta

            self._last_network_io = network_io
            self._last_timestamp = current_time

            return max(0.0, recv_rate), max(0.0, sent_rate)

        except Exception:
            logger.exception("获取网络流量速率失败")
            return 0.0, 0.0

    async def get_system_info(self) -> dict[str, str | int | float]:
        """获取系统基本信息.

        Returns:
            系统信息字典
        """
        try:
            import platform

            cpu_count = await asyncio.to_thread(psutil.cpu_count, logical=True)
            cpu_count_physical = await asyncio.to_thread(psutil.cpu_count, logical=False)
            memory = await asyncio.to_thread(psutil.virtual_memory)
            disk = await asyncio.to_thread(psutil.disk_usage, "/")

            return {
                "cpu_count": cpu_count or 0,
                "cpu_count_physical": cpu_count_physical or 0,
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "platform": platform.system(),
            }
        except Exception:
            logger.exception("获取系统信息失败")
            return {}
