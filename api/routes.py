"""API路由."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from api.models import (
    CurrentStatusResponse,
    ReservationCreate,
    ReservationResponse,
    SchedulerStatusResponse,
    SystemInfoResponse,
)
from core.monitor import SystemMonitor
from core.quota_manager import QuotaManager
from core.scheduler import CPUScheduler
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api")

# 全局实例(将在main.py中初始化)
scheduler: CPUScheduler | None = None
monitor: SystemMonitor | None = None
quota_manager: QuotaManager | None = None


def set_scheduler(sched: CPUScheduler) -> None:
    """设置调度器实例."""
    global scheduler
    scheduler = sched


def set_monitor(mon: SystemMonitor) -> None:
    """设置监控器实例."""
    global monitor
    monitor = mon


def set_quota_manager(qm: QuotaManager) -> None:
    """设置配额管理器实例."""
    global quota_manager
    quota_manager = qm


@router.get("/monitoring/current")
async def get_current_status() -> CurrentStatusResponse:
    """获取当前系统状态."""
    if not monitor or not scheduler:
        raise HTTPException(status_code=503, detail="服务未就绪")

    # 采集当前数据
    data = await monitor.collect_metrics()

    # 获取调度器状态
    status = scheduler.get_status()

    return CurrentStatusResponse(
        cpu_usage=data.cpu_usage,
        memory_usage=data.memory_usage,
        disk_io={
            "read": data.disk_io_read,
            "write": data.disk_io_write,
        },
        network={
            "in": data.network_in,
            "out": data.network_out,
        },
        window_12h_avg=status["avg_12h"],
        window_24h_peak=status["peak_24h"],
        current_limit=status["current_cpu_limit"],
        quota_remaining={
            "avg_quota": scheduler.sliding_window.get_remaining_quota(
                scheduler.settings.limits_avg_max_usage,
            ),
            "peak_quota": scheduler.peak_window.get_remaining_quota(
                scheduler.settings.limits_peak_max_duration,
            ),
        },
    )


@router.get("/scheduler/status")
async def get_scheduler_status() -> SchedulerStatusResponse:
    """获取调度器状态."""
    if not scheduler:
        raise HTTPException(status_code=503, detail="调度器未初始化")

    status = scheduler.get_status()
    return SchedulerStatusResponse(**status)


@router.get("/system/info")
async def get_system_info() -> SystemInfoResponse:
    """获取系统信息."""
    if not monitor:
        raise HTTPException(status_code=503, detail="监控器未初始化")

    info = await monitor.get_system_info()
    return SystemInfoResponse(**info)


@router.get("/reservations")
async def get_reservations() -> list[ReservationResponse]:
    """获取所有配额预留."""
    if not quota_manager:
        raise HTTPException(status_code=503, detail="配额管理器未初始化")

    reservations = await quota_manager.get_all_reservations()
    return [
        ReservationResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            start_time=r.start_time,
            end_time=r.end_time,
            cpu_quota=r.cpu_quota,
            priority=r.priority,
            enabled=r.enabled,
        )
        for r in reservations
    ]


@router.post("/reservations")
async def create_reservation(reservation: ReservationCreate) -> dict[str, str]:
    """创建配额预留."""
    if not quota_manager:
        raise HTTPException(status_code=503, detail="配额管理器未初始化")

    reservation_id = await quota_manager.create_reservation(
        name=reservation.name,
        start_time=reservation.start_time,
        end_time=reservation.end_time,
        cpu_quota=reservation.cpu_quota,
        description=reservation.description,
        priority=reservation.priority,
    )

    if not reservation_id:
        raise HTTPException(status_code=400, detail="创建预留失败")

    return {"id": reservation_id, "message": "预留创建成功"}


@router.delete("/reservations/{reservation_id}")
async def delete_reservation(reservation_id: str) -> dict[str, str]:
    """删除配额预留."""
    if not quota_manager:
        raise HTTPException(status_code=503, detail="配额管理器未初始化")

    success = await quota_manager.delete_reservation(reservation_id)
    if not success:
        raise HTTPException(status_code=404, detail="预留不存在或删除失败")

    return {"message": "预留删除成功"}


@router.get("/monitoring/history")
async def get_monitoring_history(
    hours: int = 24,
    limit: int = 1000,
) -> dict:
    """获取历史监控数据.

    Args:
        hours: 查询最近N小时的数据
        limit: 最大返回记录数
    """
    try:
        from datetime import timedelta

        from config.database import get_db

        db = get_db()
        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)

        with db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT timestamp, cpu_usage, memory_usage, disk_io_read, disk_io_write,
                       network_in, network_out
                FROM monitoring_data
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (cutoff_time.isoformat(), limit),
            )

            data = []
            for row in cursor.fetchall():
                data.append(
                    {
                        "timestamp": str(row[0]),
                        "cpu_usage": float(row[1]),
                        "memory_usage": float(row[2]),
                        "disk_io_read": float(row[3]),
                        "disk_io_write": float(row[4]),
                        "network_in": float(row[5]),
                        "network_out": float(row[6]),
                    },
                )

        return {"data": data}
    except Exception as e:
        logger.exception("获取历史数据失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取历史数据失败: {e!s}")


@router.get("/config")
async def get_config() -> dict:
    """获取当前配置."""
    try:
        from config.settings import get_settings

        settings = get_settings()

        return {
            "limits": {
                "avg_12h_limit": float(settings.limits_avg_max_usage),
                "peak_24h_limit": float(settings.limits_peak_max_duration),
                "absolute_min_cpu": float(settings.limits_absolute_min_cpu),
                "absolute_max_cpu": float(settings.limits_absolute_max_cpu),
            },
            "scheduler": {
                "interval": float(settings.scheduler_adjustment_interval),
                "quota_high_cpu_limit": float(settings.scheduler_quota_high_cpu_limit),
                "quota_medium_cpu_limit": float(settings.scheduler_quota_medium_cpu_limit),
                "quota_low_cpu_limit": float(settings.scheduler_quota_low_cpu_limit),
                "emergency_cpu_limit": float(settings.scheduler_emergency_cpu_limit),
            },
            "monitoring": {
                "interval": float(settings.monitoring_interval),
                "enable_cpu": bool(settings.monitoring_enable_cpu),
                "enable_memory": bool(settings.monitoring_enable_memory),
                "enable_disk": bool(settings.monitoring_enable_disk),
                "enable_network": bool(settings.monitoring_enable_network),
            },
            "cgroup": {
                "enabled": bool(settings.cgroup_enabled),
                "path": str(settings.cgroup_path),
            },
        }
    except Exception as e:
        logger.exception("获取配置失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取配置失败: {e!s}")


@router.put("/config")
async def update_config(config: dict) -> dict[str, str]:
    """更新配置(需要重启生效)."""
    from config.settings import get_settings

    settings = get_settings()

    # 这里只是示例,实际应该验证并保存到配置文件
    # 由于使用pydantic-settings,配置通常通过环境变量或.env文件管理

    logger.info("配置更新请求: %s", config)

    return {
        "message": "配置已更新,部分配置需要重启服务生效",
        "restart_required": "true",
    }


@router.get("/alerts")
async def get_alerts(limit: int = 100) -> dict:
    """获取告警历史."""
    try:
        from config.database import get_db

        db = get_db()

        with db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, timestamp, severity, alert_type, message, resolved
                FROM alerts
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )

            alerts = []
            for row in cursor.fetchall():
                alerts.append(
                    {
                        "id": int(row[0]),
                        "timestamp": str(row[1]),
                        "level": str(row[2]),  # severity -> level
                        "type": str(row[3]),  # alert_type -> type
                        "message": str(row[4]),
                        "resolved": bool(row[5]),
                    },
                )

        return {"alerts": alerts}
    except Exception as e:
        logger.exception("获取告警失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取告警失败: {e!s}")


@router.get("/health")
async def health_check() -> dict[str, str]:
    """健康检查."""
    return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}
