"""
性能指标采集器
"""

import time

import psutil


class MetricsCollector:
    """系统性能指标采集器"""

    def __init__(self):
        # 初始化网络和磁盘 IO 计数器
        self._last_net_io = psutil.net_io_counters()
        self._last_disk_io = psutil.disk_io_counters()
        self._last_time = time.time()
        # 初始化 CPU 百分比计数器(第一次调用返回0)
        psutil.cpu_percent(interval=None)

    def collect(self) -> dict[str, float]:
        """
        采集当前系统性能指标

        Returns:
            包含所有性能指标的字典
        """
        current_time = time.time()
        time_delta = current_time - self._last_time

        # CPU 使用率 (使用 interval=None 获取自上次调用以来的平均值,避免阻塞)
        cpu_percent = psutil.cpu_percent(interval=None)

        # 内存使用情况
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_mb = memory.used / (1024 * 1024)
        memory_total_mb = memory.total / (1024 * 1024)

        # 磁盘 IO
        current_disk_io = psutil.disk_io_counters()
        disk_read_mb_per_sec = 0.0
        disk_write_mb_per_sec = 0.0

        if self._last_disk_io and time_delta > 0:
            disk_read_bytes = current_disk_io.read_bytes - self._last_disk_io.read_bytes
            disk_write_bytes = current_disk_io.write_bytes - self._last_disk_io.write_bytes

            disk_read_mb_per_sec = (disk_read_bytes / (1024 * 1024)) / time_delta
            disk_write_mb_per_sec = (disk_write_bytes / (1024 * 1024)) / time_delta

        self._last_disk_io = current_disk_io

        # 网络 IO
        current_net_io = psutil.net_io_counters()
        network_sent_mb_per_sec = 0.0
        network_recv_mb_per_sec = 0.0

        if self._last_net_io and time_delta > 0:
            net_sent_bytes = current_net_io.bytes_sent - self._last_net_io.bytes_sent
            net_recv_bytes = current_net_io.bytes_recv - self._last_net_io.bytes_recv

            network_sent_mb_per_sec = (net_sent_bytes / (1024 * 1024)) / time_delta
            network_recv_mb_per_sec = (net_recv_bytes / (1024 * 1024)) / time_delta

        self._last_net_io = current_net_io
        self._last_time = current_time

        return {
            "cpu_percent": round(cpu_percent, 2),
            "memory_percent": round(memory_percent, 2),
            "memory_used_mb": round(memory_used_mb, 2),
            "memory_total_mb": round(memory_total_mb, 2),
            "disk_read_mb_per_sec": round(disk_read_mb_per_sec, 2),
            "disk_write_mb_per_sec": round(disk_write_mb_per_sec, 2),
            "network_sent_mb_per_sec": round(network_sent_mb_per_sec, 2),
            "network_recv_mb_per_sec": round(network_recv_mb_per_sec, 2),
        }

    def get_cpu_count(self) -> int:
        """获取 CPU 核心数"""
        count = psutil.cpu_count(logical=True)
        return count if count is not None else 1

    def get_system_info(self) -> dict[str, float]:
        """获取系统基本信息"""
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return {
            "cpu_count": float(self.get_cpu_count()),
            "total_memory_gb": round(memory.total / (1024**3), 2),
            "total_disk_gb": round(disk.total / (1024**3), 2),
        }
