"""
仪表盘相关 API
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends

from auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@router.get("/status")
async def get_dashboard_status(
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """获取仪表盘状态信息"""
    from main import cpu_scheduler, db

    # 获取最新的性能指标
    latest_metrics = db.get_latest_metrics(limit=1)
    current_metrics = latest_metrics[0] if latest_metrics else None

    # 获取调度器状态
    scheduler_status = cpu_scheduler.get_scheduler_status()

    return {
        "current_metrics": current_metrics,
        "scheduler_status": scheduler_status,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/metrics/latest")
async def get_latest_metrics(
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """获取最新的性能指标数据"""
    from main import db

    return db.get_latest_metrics(limit=limit)


@router.get("/metrics/history")
async def get_metrics_history(
    hours: int = 24,
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """获取指定时间范围的历史数据"""
    from main import db

    return db.get_metrics_in_window(hours=hours)


@router.get("/metrics/range")
async def get_metrics_by_range(
    start_time: str,
    end_time: str,
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """按时间范围查询性能指标"""
    from main import db

    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)

    return db.get_metrics_by_time_range(start_dt, end_dt)
