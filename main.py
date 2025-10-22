"""
FastAPI 主应用 - 集成 CPU 限制功能

功能:
1. 启动 FastAPI 应用
2. 在 cgroup 中运行应用
3. 自动监控和调整 CPU 限制
4. 采集性能指标

使用方法:
    sudo python main.py

要求:
- Linux 系统支持 cgroups v2
- root 权限
- Python 3.8+
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api import auth_api, config_api, dashboard
from config import ConfigManager
from database import Database
from scheduler.cpu_scheduler import CPUScheduler
from scheduler.metrics_collector import MetricsCollector

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 全局实例
db = Database()
config = ConfigManager(db)
metrics_collector = MetricsCollector()
cpu_scheduler = CPUScheduler(db, config)

# 后台任务标志
background_task_running = False

# CPU 限制相关全局变量
cpu_limiter = None
cgroup_manager = None
is_managed_mode = False


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


async def monitor_and_adjust_cpu_limit():
    """监控并调整 CPU 限制"""
    global background_task_running

    if not is_managed_mode or not cgroup_manager:
        return

    logger.info("开始监控和调整 CPU 限制")

    try:
        while background_task_running:
            try:
                # 获取调度器状态
                status = cpu_scheduler.get_scheduler_status()
                safe_limit = status["safe_cpu_limit"]
                current_limit = cgroup_manager.get_current_limit()

                # 如果差异超过 5%，则调整
                if abs(safe_limit - current_limit) > 5:
                    logger.info(
                        f"调整 CPU 限制: {current_limit:.2f}% → {safe_limit:.2f}% "
                        f"(当前CPU: {status['current_cpu_percent']:.2f}%, "
                        f"平均CPU: {status['rolling_window_avg_cpu']:.2f}%)",
                    )
                    cgroup_manager.set_cpu_limit(safe_limit)

                # 每 10 秒检查一次
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"监控错误: {e}", exc_info=True)
                await asyncio.sleep(10)

    except asyncio.CancelledError:
        logger.info("监控任务已取消")
        raise


async def metrics_collection_task():
    """后台性能指标采集任务"""
    global background_task_running
    background_task_running = True

    logger.info("性能指标采集任务启动")

    try:
        while background_task_running:
            try:
                # 采集指标
                metrics = metrics_collector.collect()

                # 保存到数据库
                db.insert_metrics(metrics)

                # 获取调度器状态
                status = cpu_scheduler.get_scheduler_status()
                logger.info(
                    f"CPU: {metrics['cpu_percent']}% | "
                    f"平均: {status['rolling_window_avg_cpu']}% | "
                    f"安全限制: {status['safe_cpu_limit']}% | "
                    f"风险: {status['risk_level']}",
                )

                # 等待下一次采集
                interval = config.metrics_interval_seconds
                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"指标采集错误: {e}", exc_info=True)
                await asyncio.sleep(10)  # 错误后等待 10 秒重试

    except asyncio.CancelledError:
        logger.info("性能指标采集任务已取消")
        raise


async def cleanup_task():
    """后台数据清理任务"""
    logger.info("数据清理任务启动")

    try:
        while background_task_running:
            try:
                # 每天清理一次过期数据
                retention_days = config.history_retention_days
                db.cleanup_old_metrics(retention_days)
                logger.info(f"清理了 {retention_days} 天前的历史数据")

                # 等待 24 小时
                await asyncio.sleep(86400)

            except Exception as e:
                logger.error(f"数据清理错误: {e}", exc_info=True)
                await asyncio.sleep(3600)  # 错误后等待 1 小时重试

    except asyncio.CancelledError:
        logger.info("数据清理任务已取消")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("应用启动中...")

    # 启动后台任务
    metrics_task = asyncio.create_task(metrics_collection_task())
    cleanup_task_handle = asyncio.create_task(cleanup_task())
    monitor_task = asyncio.create_task(monitor_and_adjust_cpu_limit())

    yield

    # 关闭时
    logger.info("应用关闭中...")
    global background_task_running
    background_task_running = False

    # 取消后台任务
    metrics_task.cancel()
    cleanup_task_handle.cancel()
    monitor_task.cancel()

    # 等待任务取消完成（最多等待2秒）
    try:
        await asyncio.wait_for(
            asyncio.gather(metrics_task, cleanup_task_handle, monitor_task, return_exceptions=True),
            timeout=2.0,
        )
    except TimeoutError:
        logger.warning("后台任务取消超时")

    # 清理 cgroup
    if is_managed_mode and cgroup_manager:
        cgroup_manager.cleanup()

    logger.info("应用已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="CPU 智能调度与性能监控系统",
    description="Linux 服务器 CPU 智能调度与性能监控系统",
    version="1.0.0",
    lifespan=lifespan,
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 模板引擎
templates = Jinja2Templates(directory="templates")


# 依赖注入
def get_db():
    return db


def get_config():
    return config


# 注册 API 路由
app.include_router(auth_api.router)
app.include_router(dashboard.router)
app.include_router(config_api.router)


# 页面路由
@app.get("/", response_class=HTMLResponse)
async def root():
    """重定向到登录页"""
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """仪表盘页面"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """配置管理页面"""
    return templates.TemplateResponse("config.html", {"request": request})


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """历史数据查询页面"""
    return templates.TemplateResponse("history.html", {"request": request})


# 健康检查
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "background_task_running": background_task_running,
    }


def init_cgroup_management():
    """初始化 cgroup 管理"""
    global cgroup_manager, is_managed_mode

    # 检查 root 权限
    if os.geteuid() != 0:
        logger.error("错误: 需要 root 权限来管理 cgroups")
        logger.error("请使用: sudo python main.py")
        sys.exit(1)

    # 检查 cgroups v2 支持
    if not Path("/sys/fs/cgroup/cgroup.controllers").exists():
        logger.error("错误: 系统不支持 cgroups v2")
        sys.exit(1)

    # 初始化 cgroup 管理器
    try:
        cgroup_manager = CGroupManager()
        cgroup_manager.setup()

        # 设置初始 CPU 限制
        initial_limit = config.avg_load_limit_percent
        cgroup_manager.set_cpu_limit(initial_limit)
        logger.info(f"初始 CPU 限制: {initial_limit}%")

        is_managed_mode = True
        logger.info("CPU 限制管理已启用")

    except Exception as e:
        logger.error(f"初始化 cgroup 失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    import uvicorn

    # 初始化 cgroup 管理
    init_cgroup_management()

    uvicorn.run(app, host="0.0.0.0", port=8000)
