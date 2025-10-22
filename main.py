"""
FastAPI 主应用
"""

import asyncio
import logging
from contextlib import asynccontextmanager

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


async def metrics_collection_task():
    """后台性能指标采集任务"""
    global background_task_running
    background_task_running = True

    logger.info("性能指标采集任务启动")

    while background_task_running:
        try:
            # 采集指标
            metrics = metrics_collector.collect()

            # 保存到数据库
            db.insert_metrics(metrics)

            # 检查是否需要限制 CPU
            should_throttle, reason = cpu_scheduler.should_throttle_cpu(metrics["cpu_percent"])
            if should_throttle:
                logger.warning(f"CPU 限制建议: {reason}")

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


async def cleanup_task():
    """后台数据清理任务"""
    logger.info("数据清理任务启动")

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("应用启动中...")

    # 启动后台任务
    metrics_task = asyncio.create_task(metrics_collection_task())
    cleanup_task_handle = asyncio.create_task(cleanup_task())

    yield

    # 关闭时
    logger.info("应用关闭中...")
    global background_task_running
    background_task_running = False

    # 等待后台任务结束
    await asyncio.gather(metrics_task, cleanup_task_handle, return_exceptions=True)


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
