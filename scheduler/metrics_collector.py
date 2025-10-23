"""
性能指标采集器
"""

import time
from pathlib import Path

import psutil


class MetricsCollector:
    """系统性能指标采集器（支持 system/cgroup 两种 CPU 采样口径）"""

    def __init__(self):
        # 初始化网络和磁盘 IO 计数器
        self._last_net_io = psutil.net_io_counters()
        self._last_disk_io = psutil.disk_io_counters()
        self._last_time = time.time()

        # CPU 采样模式：system 或 cgroup
        self._cpu_mode: str = "system"
        self._cgroup_path: Path | None = None
        self._prev_cg_usage_usec: int | None = None
        self._prev_cg_time: float | None = None

        # system 模式下初始化 CPU 百分比计数器(第一次调用返回0)
        psutil.cpu_percent(interval=None)

    def enable_cgroup_mode(self, cgroup_path: Path):
        """启用 cgroup 口径 CPU 采样（使用 cpu.stat 的 usage_usec 计算）。"""
        self._cpu_mode = "cgroup"
        self._cgroup_path = cgroup_path
        self._prev_cg_usage_usec = None
        self._prev_cg_time = None

    def _read_cgroup_usage_usec(self) -> int:
        """读取 cgroup v2 cpu.stat 中的 usage_usec。"""
        assert self._cgroup_path is not None
        stat_path = self._cgroup_path / "cpu.stat"
        content = stat_path.read_text().splitlines()
        for line in content:
            if line.startswith("usage_usec "):
                return int(line.split()[1])
        # 某些内核字段名可能略有不同，这里保守返回0
        return 0

    def _calc_cgroup_cpu_percent(self, now_time: float) -> float:
        usage_usec = self._read_cgroup_usage_usec()
        if self._prev_cg_usage_usec is None or self._prev_cg_time is None:
            # 首次采样仅建立基线
            self._prev_cg_usage_usec = usage_usec
            self._prev_cg_time = now_time
            return 0.0

        delta_usage = max(0, usage_usec - self._prev_cg_usage_usec)
        delta_time = max(1e-6, now_time - self._prev_cg_time)
        cpu_count = psutil.cpu_count(logical=True) or 1

        # usage_usec 是微秒；总可用 CPU 时间 = delta_time(秒) * 1e6 * cpu_count
        percent = (delta_usage / (delta_time * 1_000_000 * cpu_count)) * 100.0

        # 更新基线
        self._prev_cg_usage_usec = usage_usec
        self._prev_cg_time = now_time

        # 约束在 0~100
        if percent < 0:
            percent = 0.0
        elif percent > 100:
            percent = 100.0
        return percent

    def collect(self) -> dict[str, float]:
        """
        采集当前系统性能指标（CPU 百分比按当前模式采样：system 或 cgroup）

        Returns:
            包含所有性能指标的字典
        """
        current_time = time.time()
        time_delta = current_time - self._last_time

        # CPU 使用率
        if self._cpu_mode == "cgroup" and self._cgroup_path is not None:
            cpu_percent = self._calc_cgroup_cpu_percent(current_time)
        else:
            # system 模式使用 psutil 的非阻塞采样
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
            "cpu_percent": round(cpu_percent, 2),  # 口径与 _cpu_mode 一致
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
