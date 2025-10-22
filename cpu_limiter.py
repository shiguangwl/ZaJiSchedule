#!/usr/bin/env python3
"""
CPU 限制器 - 使用 cgroups v2 动态限制 CPU 使用率

功能:
1. 根据调度器的建议动态调整 cgroups CPU 配额
2. 自动创建和管理 cgroups
3. 实时监控和调整 CPU 限制

使用方法:
    sudo python cpu_limiter.py

要求:
- Linux 系统支持 cgroups v2
- root 权限
- Python 3.8+
"""

import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path

from config import Config
from database import Database
from scheduler.cpu_scheduler import CPUScheduler

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class CGroupCPULimiter:
    """使用 cgroups v2 限制 CPU 使用率"""

    def __init__(self, cgroup_name: str = "zajischedule"):
        """
        初始化 CPU 限制器

        Args:
            cgroup_name: cgroup 名称
        """
        self.cgroup_name = cgroup_name
        self.cgroup_path = Path(f"/sys/fs/cgroup/{cgroup_name}")
        self.cpu_max_file = self.cgroup_path / "cpu.max"
        self.procs_file = self.cgroup_path / "cgroup.procs"

        # 检查是否有 root 权限
        if os.geteuid() != 0:
            raise PermissionError("需要 root 权限来管理 cgroups")

        # 检查 cgroups v2 是否可用
        if not Path("/sys/fs/cgroup/cgroup.controllers").exists():
            raise RuntimeError("系统不支持 cgroups v2")

    def setup_cgroup(self) -> None:
        """创建并配置 cgroup"""
        try:
            # 创建 cgroup 目录
            if not self.cgroup_path.exists():
                self.cgroup_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"创建 cgroup: {self.cgroup_path}")

            # 启用 CPU 控制器
            controllers_file = Path("/sys/fs/cgroup/cgroup.subtree_control")
            current_controllers = controllers_file.read_text().strip()
            if "cpu" not in current_controllers:
                controllers_file.write_text("+cpu")
                logger.info("启用 CPU 控制器")

            logger.info("cgroup 设置完成")

        except Exception as e:
            logger.error(f"设置 cgroup 失败: {e}")
            raise

    def set_cpu_limit(self, cpu_percent: float) -> None:
        """
        设置 CPU 限制

        Args:
            cpu_percent: CPU 使用率限制 (0-100)

        cgroups v2 cpu.max 格式: "quota period"
        - quota: 在 period 时间内可以使用的 CPU 时间（微秒）
        - period: 时间周期（微秒），通常是 100000 (100ms)

        例如:
        - 30% CPU: "30000 100000"
        - 50% CPU: "50000 100000"
        - 100% CPU: "100000 100000" 或 "max 100000"
        """
        try:
            # 限制在 0-100 之间
            cpu_percent = max(0, min(100, cpu_percent))

            # 计算配额
            period = 100000  # 100ms
            quota = int(cpu_percent * period / 100)

            # 写入 cpu.max
            cpu_max_value = f"{quota} {period}"
            self.cpu_max_file.write_text(cpu_max_value)

            logger.info(f"设置 CPU 限制: {cpu_percent:.2f}% (quota={quota}, period={period})")

        except Exception as e:
            logger.error(f"设置 CPU 限制失败: {e}")
            raise

    def add_process(self, pid: int) -> None:
        """
        将进程添加到 cgroup

        Args:
            pid: 进程 ID
        """
        try:
            self.procs_file.write_text(str(pid))
            logger.info(f"将进程 {pid} 添加到 cgroup")

        except Exception as e:
            logger.error(f"添加进程到 cgroup 失败: {e}")
            raise

    def get_current_limit(self) -> float:
        """
        获取当前 CPU 限制

        Returns:
            当前 CPU 限制百分比
        """
        try:
            cpu_max_value = self.cpu_max_file.read_text().strip()
            if cpu_max_value.startswith("max"):
                return 100.0

            quota, period = map(int, cpu_max_value.split())
            return (quota / period) * 100

        except Exception as e:
            logger.error(f"获取当前 CPU 限制失败: {e}")
            return 0.0

    def cleanup(self) -> None:
        """清理 cgroup"""
        try:
            if self.cgroup_path.exists():
                # 移除所有进程
                procs = self.procs_file.read_text().strip().split("\n")
                for proc in procs:
                    if proc:
                        logger.info(f"从 cgroup 移除进程: {proc}")

                # 删除 cgroup 目录
                self.cgroup_path.rmdir()
                logger.info(f"删除 cgroup: {self.cgroup_path}")

        except Exception as e:
            logger.warning(f"清理 cgroup 失败: {e}")


class DynamicCPUScheduler:
    """动态 CPU 调度器 - 结合调度算法和 cgroups 限制"""

    def __init__(
        self,
        limiter: CGroupCPULimiter,
        scheduler: CPUScheduler,
        config: Config,
        update_interval: int = 10,
    ):
        """
        初始化动态调度器

        Args:
            limiter: CPU 限制器
            scheduler: CPU 调度器
            config: 配置
            update_interval: 更新间隔（秒）
        """
        self.limiter = limiter
        self.scheduler = scheduler
        self.config = config
        self.update_interval = update_interval
        self.running = False

    async def start(self) -> None:
        """启动动态调度"""
        self.running = True
        logger.info("动态 CPU 调度器启动")

        try:
            while self.running:
                # 获取调度器状态
                status = self.scheduler.get_scheduler_status()

                # 获取安全 CPU 限制
                safe_limit = status["safe_cpu_limit"]
                current_cpu = status["current_cpu_percent"]
                avg_cpu = status["rolling_window_avg_cpu"]

                # 获取当前 cgroup 限制
                current_limit = self.limiter.get_current_limit()

                # 决定是否需要调整限制
                # 策略: 使用安全限制作为 cgroup 的硬限制
                target_limit = safe_limit

                # 如果目标限制与当前限制差异超过 5%，则调整
                if abs(target_limit - current_limit) > 5:
                    logger.info(
                        f"调整 CPU 限制: {current_limit:.2f}% → {target_limit:.2f}% "
                        f"(当前CPU: {current_cpu:.2f}%, 平均CPU: {avg_cpu:.2f}%)"
                    )
                    self.limiter.set_cpu_limit(target_limit)
                else:
                    logger.debug(
                        f"CPU 限制无需调整: {current_limit:.2f}% "
                        f"(当前CPU: {current_cpu:.2f}%, 平均CPU: {avg_cpu:.2f}%)"
                    )

                # 等待下一次更新
                await asyncio.sleep(self.update_interval)

        except asyncio.CancelledError:
            logger.info("动态 CPU 调度器已取消")
            raise
        except Exception as e:
            logger.error(f"动态 CPU 调度器错误: {e}", exc_info=True)
            raise

    def stop(self) -> None:
        """停止动态调度"""
        self.running = False
        logger.info("动态 CPU 调度器停止")


async def main():
    """主函数"""
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("用法: sudo python cpu_limiter.py <target_pid>")
        print("  target_pid: 要限制的进程 ID")
        sys.exit(1)

    target_pid = int(sys.argv[1])

    # 检查进程是否存在
    try:
        os.kill(target_pid, 0)
    except OSError:
        print(f"错误: 进程 {target_pid} 不存在")
        sys.exit(1)

    # 初始化组件
    config = Config()
    db = Database()
    scheduler = CPUScheduler(db, config)
    limiter = CGroupCPULimiter()

    try:
        # 设置 cgroup
        limiter.setup_cgroup()

        # 将目标进程添加到 cgroup
        limiter.add_process(target_pid)

        # 设置初始 CPU 限制
        initial_limit = config.avg_load_limit_percent
        limiter.set_cpu_limit(initial_limit)
        logger.info(f"初始 CPU 限制: {initial_limit}%")

        # 启动动态调度器
        dynamic_scheduler = DynamicCPUScheduler(limiter, scheduler, config)
        await dynamic_scheduler.start()

    except KeyboardInterrupt:
        logger.info("收到中断信号，正在清理...")
    except Exception as e:
        logger.error(f"运行错误: {e}", exc_info=True)
    finally:
        # 清理 cgroup
        limiter.cleanup()
        logger.info("CPU 限制器已停止")


if __name__ == "__main__":
    asyncio.run(main())

