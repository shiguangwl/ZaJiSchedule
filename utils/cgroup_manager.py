"""cgroup资源控制管理."""

import os
from pathlib import Path

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


class CGroupManager:
    """cgroup v2管理器.

    用于动态调整CPU配额限制.
    """

    def __init__(self) -> None:
        """初始化cgroup管理器."""
        self.settings = get_settings()
        self.cgroup_path = Path(self.settings.cgroup_path)
        self.cpu_max_file = self.cgroup_path / "cpu.max"
        self.procs_file = self.cgroup_path / "cgroup.procs"

        # CPU周期(微秒),标准值为100000(100ms)
        self.cpu_period = 100000

        self._initialized = False
        self._current_limit: float | None = None

        logger.info("初始化cgroup管理器: path=%s", self.cgroup_path)

    def initialize(self) -> bool:
        """初始化cgroup.

        Returns:
            是否成功初始化
        """
        if not self.settings.cgroup_enabled:
            logger.warning("cgroup控制已禁用")
            return False

        if self._initialized:
            return True

        try:
            # 检查是否有root权限
            if os.geteuid() != 0:
                logger.error("需要root权限才能操作cgroup")
                return False

            # 检查cgroup v2是否可用
            cgroup_root = Path("/sys/fs/cgroup")
            if not cgroup_root.exists():
                logger.error("cgroup文件系统不存在")
                return False

            # 创建cgroup目录
            if not self.cgroup_path.exists():
                self.cgroup_path.mkdir(parents=True, exist_ok=True)
                logger.info("创建cgroup目录: %s", self.cgroup_path)

            # 验证cpu.max文件存在
            if not self.cpu_max_file.exists():
                logger.error("cpu.max文件不存在,可能不支持cgroup v2")
                return False

            self._initialized = True
            logger.info("cgroup初始化成功")
            return True

        except Exception:
            logger.exception("初始化cgroup失败")
            return False

    def set_cpu_limit(self, limit_percent: float) -> bool:
        """设置CPU限制.

        Args:
            limit_percent: CPU限制百分比(0-100)

        Returns:
            是否成功设置
        """
        if not self._initialized:
            if not self.initialize():
                return False

        try:
            # 限制范围检查
            limit_percent = max(
                self.settings.limits_absolute_min_cpu,
                min(limit_percent, self.settings.limits_absolute_max_cpu),
            )

            # 计算quota值(微秒)
            # quota = period * (limit_percent / 100)
            quota = int(self.cpu_period * (limit_percent / 100.0))

            # 写入cpu.max文件
            # 格式: "quota period"
            cpu_max_value = f"{quota} {self.cpu_period}\n"
            self.cpu_max_file.write_text(cpu_max_value, encoding="utf-8")

            self._current_limit = limit_percent
            logger.info(
                "设置CPU限制: %.1f%% (quota=%d, period=%d)",
                limit_percent,
                quota,
                self.cpu_period,
            )
            return True

        except PermissionError:
            logger.error("没有权限写入cpu.max文件,需要root权限")
            return False
        except Exception:
            logger.exception("设置CPU限制失败")
            return False

    def get_current_limit(self) -> float | None:
        """获取当前CPU限制.

        Returns:
            当前CPU限制百分比,如果无法获取则返回None
        """
        if not self._initialized:
            return None

        try:
            content = self.cpu_max_file.read_text(encoding="utf-8").strip()
            if content == "max":
                return 100.0

            parts = content.split()
            if len(parts) != 2:
                return None

            quota = int(parts[0])
            period = int(parts[1])

            limit_percent = (quota / period) * 100.0
            return limit_percent

        except Exception:
            logger.exception("获取当前CPU限制失败")
            return None

    def add_process(self, pid: int) -> bool:
        """将进程添加到cgroup.

        Args:
            pid: 进程ID

        Returns:
            是否成功添加
        """
        if not self._initialized:
            if not self.initialize():
                return False

        try:
            # 写入进程ID到cgroup.procs
            self.procs_file.write_text(f"{pid}\n", encoding="utf-8")
            logger.info("将进程 %d 添加到cgroup", pid)
            return True

        except PermissionError:
            logger.error("没有权限写入cgroup.procs文件")
            return False
        except Exception:
            logger.exception("添加进程到cgroup失败")
            return False

    def add_current_process(self) -> bool:
        """将当前进程添加到cgroup.

        Returns:
            是否成功添加
        """
        return self.add_process(os.getpid())

    def remove_cpu_limit(self) -> bool:
        """移除CPU限制(设置为max).

        Returns:
            是否成功移除
        """
        if not self._initialized:
            return False

        try:
            self.cpu_max_file.write_text("max 100000\n", encoding="utf-8")
            self._current_limit = 100.0
            logger.info("移除CPU限制")
            return True

        except Exception:
            logger.exception("移除CPU限制失败")
            return False

    def is_available(self) -> bool:
        """检查cgroup是否可用.

        Returns:
            cgroup是否可用
        """
        if not self.settings.cgroup_enabled:
            return False

        if os.geteuid() != 0:
            return False

        return self.cgroup_path.exists() and self.cpu_max_file.exists()

