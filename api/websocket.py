"""WebSocket实时推送."""

import asyncio
import json
from datetime import UTC, datetime

from config.settings import get_settings
from core.monitor import SystemMonitor
from core.scheduler import CPUScheduler
from utils.logger import get_logger
from fastapi import WebSocket, WebSocketDisconnect

logger = get_logger(__name__)


class ConnectionManager:
    """WebSocket连接管理器."""

    def __init__(self) -> None:
        """初始化连接管理器."""
        self.active_connections: list[WebSocket] = []
        self.settings = get_settings()

    async def connect(self, websocket: WebSocket) -> None:
        """接受新连接.

        Args:
            websocket: WebSocket连接
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("新WebSocket连接,当前连接数: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """断开连接.

        Args:
            websocket: WebSocket连接
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WebSocket连接断开,当前连接数: %d", len(self.active_connections))

    async def broadcast(self, message: dict) -> None:
        """广播消息到所有连接.

        Args:
            message: 消息内容
        """
        if not self.active_connections:
            return

        # 转换为JSON
        message_json = json.dumps(message, default=str)

        # 发送到所有连接
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                logger.exception("发送WebSocket消息失败")
                disconnected.append(connection)

        # 清理断开的连接
        for connection in disconnected:
            self.disconnect(connection)


# 全局连接管理器
manager = ConnectionManager()


async def websocket_endpoint(
    websocket: WebSocket,
    scheduler: CPUScheduler,
    monitor: SystemMonitor,
) -> None:
    """WebSocket端点.

    Args:
        websocket: WebSocket连接
        scheduler: 调度器实例
        monitor: 监控器实例
    """
    await manager.connect(websocket)

    try:
        # 发送初始状态
        await send_initial_state(websocket, scheduler, monitor)

        # 保持连接,等待客户端消息
        while True:
            try:
                # 接收客户端消息(心跳等)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0,
                )
                # 处理客户端消息
                await handle_client_message(websocket, data)
            except TimeoutError:
                # 发送心跳
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        logger.exception("WebSocket连接异常")
        manager.disconnect(websocket)


async def send_initial_state(
    websocket: WebSocket,
    scheduler: CPUScheduler,
    monitor: SystemMonitor,
) -> None:
    """发送初始状态.

    Args:
        websocket: WebSocket连接
        scheduler: 调度器实例
        monitor: 监控器实例
    """
    try:
        # 获取当前状态
        monitoring_data = await monitor.collect_metrics()
        scheduler_status = scheduler.get_status()

        # 发送初始状态
        await websocket.send_json(
            {
                "type": "initial_state",
                "data": {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "cpu_usage": monitoring_data.cpu_usage,
                    "memory_usage": monitoring_data.memory_usage,
                    "current_limit": scheduler_status["current_cpu_limit"],
                    "avg_12h": scheduler_status["avg_12h"],
                    "peak_24h": scheduler_status["peak_24h"],
                },
            },
        )
    except Exception:
        logger.exception("发送初始状态失败")


async def handle_client_message(_websocket: WebSocket, message: str) -> None:
    """处理客户端消息.

    Args:
        websocket: WebSocket连接
        message: 消息内容
    """
    try:
        data = json.loads(message)
        msg_type = data.get("type")

        if msg_type == "pong":
            # 心跳响应
            pass
        else:
            logger.warning("未知的消息类型: %s", msg_type)

    except json.JSONDecodeError:
        logger.exception("无效的JSON消息: %s", message)
    except Exception:
        logger.exception("处理客户端消息失败")


async def broadcast_monitoring_update(
    scheduler: CPUScheduler,
    monitor: SystemMonitor,
) -> None:
    """广播监控更新.

    Args:
        scheduler: 调度器实例
        monitor: 监控器实例
    """
    settings = get_settings()

    while True:
        try:
            # 采集数据
            monitoring_data = await monitor.collect_metrics()
            scheduler_status = scheduler.get_status()

            # 广播更新
            await manager.broadcast(
                {
                    "type": "monitoring_update",
                    "data": {
                        "timestamp": monitoring_data.timestamp.isoformat(),
                        "cpu_usage": monitoring_data.cpu_usage,
                        "memory_usage": monitoring_data.memory_usage,
                        "disk_io_read": monitoring_data.disk_io_read,
                        "disk_io_write": monitoring_data.disk_io_write,
                        "network_in": monitoring_data.network_in,
                        "network_out": monitoring_data.network_out,
                        "current_limit": scheduler_status["current_cpu_limit"],
                        "avg_12h": scheduler_status["avg_12h"],
                        "peak_24h": scheduler_status["peak_24h"],
                        "quota_remaining": {
                            "avg": scheduler.sliding_window.get_remaining_quota(
                                settings.limits_avg_max_usage,
                            ),
                            "peak": scheduler.peak_window.get_remaining_quota(
                                settings.limits_peak_max_duration,
                            ),
                        },
                    },
                },
            )

            # 等待下一次推送
            await asyncio.sleep(settings.ws_push_interval)

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("广播监控更新失败")
            await asyncio.sleep(settings.ws_push_interval)
