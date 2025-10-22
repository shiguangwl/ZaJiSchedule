#!/usr/bin/env python3
"""
托管启动脚本 - 自动启动应用并应用 CPU 限制

功能:
1. 在 cgroup 中启动主应用
2. 自动监控和调整 CPU 限制
3. 优雅关闭

使用方法:
    sudo python start_managed.py

要求:
- Linux 系统支持 cgroups v2
- root 权限
- Python 3.8+
"""

import asyncio
import logging
import os
import signal
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
    handlers=[
        logging.FileHandler("logs/managed_start.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class CGroupManager:
    """cgroup 管理器"""

    def __init__(self, cgroup_name: str = "zajischedule"):
        self.cgroup_name = cgroup_name
        self.cgroup_path = Path(f"/sys/fs/cgroup/{cgroup_name}")
        self.cpu_max_file = self.cgroup_path / "cpu.max"
        self.procs_file = self.cgroup_path / "cgroup.procs"

    def setup(self) -> None:
        """设置 cgroup"""
        try:
            # 创建 cgroup
            if not self.cgroup_path.exists():
                self.cgroup_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"创建 cgroup: {self.cgroup_path}")

            # 启用 CPU 控制器
            controllers_file = Path("/sys/fs/cgroup/cgroup.subtree_control")
            current_controllers = controllers_file.read_text().strip()
            if "cpu" not in current_controllers:
                controllers_file.write_text("+cpu")
                logger.info("启用 CPU 控制器")

        except Exception as e:
            logger.error(f"设置 cgroup 失败: {e}")
            raise

    def set_cpu_limit(self, cpu_percent: float) -> None:
        """设置 CPU 限制"""
        try:
            cpu_percent = max(0, min(100, cpu_percent))
            period = 100000
            quota = int(cpu_percent * period / 100)
            self.cpu_max_file.write_text(f"{quota} {period}")
            logger.info(f"设置 CPU 限制: {cpu_percent:.2f}%")
        except Exception as e:
            logger.error(f"设置 CPU 限制失败: {e}")

    def get_current_limit(self) -> float:
        """获取当前 CPU 限制"""
        try:
            cpu_max_value = self.cpu_max_file.read_text().strip()
            if cpu_max_value.startswith("max"):
                return 100.0
            quota, period = map(int, cpu_max_value.split())
            return (quota / period) * 100
        except Exception:
            return 0.0

    def cleanup(self) -> None:
        """清理 cgroup"""
        try:
            if self.cgroup_path.exists():
                # 移除所有进程到根 cgroup
                if self.procs_file.exists():
                    procs = self.procs_file.read_text().strip().split("\n")
                    root_procs = Path("/sys/fs/cgroup/cgroup.procs")
                    for proc in procs:
                        if proc:
                            try:
                                root_procs.write_text(proc)
                            except Exception:
                                pass

                # 删除 cgroup
                self.cgroup_path.rmdir()
                logger.info("cgroup 已清理")
        except Exception as e:
            logger.warning(f"清理 cgroup 失败: {e}")


class ManagedApplication:
    """托管应用程序"""

    def __init__(self):
        self.config = Config()
        self.db = Database()
        self.scheduler = CPUScheduler(self.db, self.config)
        self.cgroup_manager = CGroupManager()
        self.app_process = None
        self.running = False

    async def start_app(self) -> None:
        """在 cgroup 中启动应用"""
        try:
            # 设置 cgroup
            self.cgroup_manager.setup()

            # 设置初始 CPU 限制
            initial_limit = self.config.avg_load_limit_percent
            self.cgroup_manager.set_cpu_limit(initial_limit)

            # 启动应用进程
            python_path = sys.executable
            script_dir = Path(__file__).parent
            main_script = script_dir / "main.py"

            logger.info(f"启动应用: {python_path} {main_script}")

            # 使用 systemd-run 在 cgroup 中启动（如果可用）
            # 否则手动启动并添加到 cgroup
            try:
                # 尝试使用 systemd-run
                cmd = [
                    "systemd-run",
                    "--scope",
                    "--unit=zajischedule-app",
                    f"--slice={self.cgroup_manager.cgroup_name}",
                    python_path,
                    str(main_script),
                ]
                self.app_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                logger.info("使用 systemd-run 启动应用")

            except FileNotFoundError:
                # systemd-run 不可用，手动启动
                self.app_process = subprocess.Popen(
                    [python_path, str(main_script)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                # 将进程添加到 cgroup
                await asyncio.sleep(1)  # 等待进程启动
                self.cgroup_manager.procs_file.write_text(str(self.app_process.pid))
                logger.info(f"手动将进程 {self.app_process.pid} 添加到 cgroup")

            logger.info(f"应用已启动 (PID: {self.app_process.pid})")

        except Exception as e:
            logger.error(f"启动应用失败: {e}", exc_info=True)
            raise

    async def monitor_and_adjust(self) -> None:
        """监控并调整 CPU 限制"""
        self.running = True
        logger.info("开始监控和调整 CPU 限制")

        try:
            while self.running:
                # 检查应用进程是否还在运行
                if self.app_process and self.app_process.poll() is not None:
                    logger.error("应用进程已退出")
                    break

                # 获取调度器状态
                status = self.scheduler.get_scheduler_status()
                safe_limit = status["safe_cpu_limit"]
                current_limit = self.cgroup_manager.get_current_limit()

                # 如果差异超过 5%，则调整
                if abs(safe_limit - current_limit) > 5:
                    logger.info(
                        f"调整 CPU 限制: {current_limit:.2f}% → {safe_limit:.2f}% "
                        f"(当前CPU: {status['current_cpu_percent']:.2f}%, "
                        f"平均CPU: {status['rolling_window_avg_cpu']:.2f}%)"
                    )
                    self.cgroup_manager.set_cpu_limit(safe_limit)

                # 每 10 秒检查一次
                await asyncio.sleep(10)

        except asyncio.CancelledError:
            logger.info("监控任务已取消")
            raise
        except Exception as e:
            logger.error(f"监控错误: {e}", exc_info=True)
            raise

    async def stop(self) -> None:
        """停止应用"""
        logger.info("正在停止应用...")
        self.running = False

        # 停止应用进程
        if self.app_process:
            try:
                self.app_process.terminate()
                await asyncio.sleep(2)
                if self.app_process.poll() is None:
                    self.app_process.kill()
                logger.info("应用进程已停止")
            except Exception as e:
                logger.error(f"停止应用进程失败: {e}")

        # 清理 cgroup
        self.cgroup_manager.cleanup()

    async def run(self) -> None:
        """运行托管应用"""
        try:
            # 启动应用
            await self.start_app()

            # 等待应用启动
            await asyncio.sleep(3)

            # 开始监控和调整
            await self.monitor_and_adjust()

        except KeyboardInterrupt:
            logger.info("收到中断信号")
        except Exception as e:
            logger.error(f"运行错误: {e}", exc_info=True)
        finally:
            await self.stop()


async def main():
    """主函数"""
    # 检查 root 权限
    if os.geteuid() != 0:
        print("错误: 需要 root 权限")
        print("请使用: sudo python start_managed.py")
        sys.exit(1)

    # 检查 cgroups v2
    if not Path("/sys/fs/cgroup/cgroup.controllers").exists():
        print("错误: 系统不支持 cgroups v2")
        sys.exit(1)

    # 创建日志目录
    Path("logs").mkdir(exist_ok=True)

    # 运行托管应用
    app = ManagedApplication()

    # 设置信号处理
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("收到停止信号")
        asyncio.create_task(app.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # 运行
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())

