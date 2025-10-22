"""CPU智能调度系统主程序."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from api import routes, websocket
from config.database import get_db
from config.settings import get_settings
from core.monitor import SystemMonitor
from core.quota_manager import QuotaManager
from core.scheduler import CPUScheduler
from utils.logger import get_logger, setup_logging

# 设置日志
setup_logging()
logger = get_logger(__name__)

# 全局实例
scheduler: CPUScheduler | None = None
monitor: SystemMonitor | None = None
quota_manager: QuotaManager | None = None
broadcast_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理.

    Args:
        app: FastAPI应用实例

    Yields:
        None
    """
    global scheduler, monitor, quota_manager, broadcast_task

    logger.info("启动CPU智能调度系统")

    # 初始化数据库
    get_db()
    logger.info("数据库初始化完成")

    # 初始化组件
    scheduler = CPUScheduler()
    monitor = SystemMonitor()
    quota_manager = QuotaManager()

    # 设置API路由的全局实例
    routes.set_scheduler(scheduler)
    routes.set_monitor(monitor)
    routes.set_quota_manager(quota_manager)

    # 启动调度器
    await scheduler.start()

    # 启动WebSocket广播任务
    broadcast_task = asyncio.create_task(
        websocket.broadcast_monitoring_update(scheduler, monitor),
    )

    logger.info("系统启动完成")

    yield

    # 关闭时清理
    logger.info("正在关闭系统...")

    if broadcast_task:
        broadcast_task.cancel()
        try:
            await broadcast_task
        except asyncio.CancelledError:
            pass

    if scheduler:
        await scheduler.stop()

    logger.info("系统已关闭")


# 创建FastAPI应用
app = FastAPI(
    title="CPU智能调度系统",
    description="基于滑动窗口算法的Linux服务器CPU智能调度系统",
    version="1.0.0",
    lifespan=lifespan,
)

# 注册API路由
app.include_router(routes.router)

# 静态文件
web_dir = Path(__file__).parent / "web"
if (web_dir / "static").exists():
    app.mount("/static", StaticFiles(directory=str(web_dir / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """主页."""
    index_file = web_dir / "templates" / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>CPU智能调度系统</h1><p>前端界面开发中...</p>")


@app.websocket("/ws/monitoring")
async def websocket_monitoring(ws: WebSocket) -> None:
    """WebSocket监控端点."""
    if not scheduler or not monitor:
        await ws.close(code=1011, reason="服务未就绪")
        return

    await websocket.websocket_endpoint(ws, scheduler, monitor)


def main() -> None:
    """主函数."""
    settings = get_settings()

    logger.info(
        "启动Web服务: host=%s, port=%d",
        settings.server_host,
        settings.server_port,
    )

    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.server_debug,
        log_level="info",
    )


if __name__ == "__main__":
    main()
