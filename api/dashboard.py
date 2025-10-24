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
    import sys

    # 使用 __main__ 模块而不是 main 模块
    main_module = sys.modules["__main__"]

    # 获取最新的性能指标
    latest_metrics = main_module.db.get_latest_metrics(limit=1)
    current_metrics = latest_metrics[0] if latest_metrics else None

    # 获取调度器状态
    scheduler_status = main_module.cpu_scheduler.get_scheduler_status()

    # 已应用限制（归一化CPU%）
    import logging

    logger = logging.getLogger(__name__)
    applied_limit = None
    try:
        if main_module.is_managed_mode and main_module.cgroup_manager:
            applied_limit = main_module.cgroup_manager.get_current_limit()
            logger.debug(f"成功获取已应用CPU限制: {applied_limit}%")
        else:
            logger.debug(
                f"无法获取CPU限制: is_managed_mode={main_module.is_managed_mode}, "
                f"cgroup_manager={'存在' if main_module.cgroup_manager else '不存在'}",
            )
    except Exception as e:
        logger.error(f"获取已应用CPU限制失败: {e}", exc_info=True)
        applied_limit = None

    scheduler_status["applied_cpu_limit"] = applied_limit

    return {
        "current_metrics": current_metrics,
        "scheduler_status": scheduler_status,
        "is_managed_mode": main_module.is_managed_mode,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/metrics/latest")
async def get_latest_metrics(
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """获取最新的性能指标数据"""
    import main

    return main.db.get_latest_metrics(limit=limit)


@router.get("/metrics/history")
async def get_metrics_history(
    hours: int = 24,
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """获取指定时间范围的历史数据"""
    import main

    return main.db.get_metrics_in_window(hours=hours)


@router.get("/metrics/range")
async def get_metrics_by_range(
    start_time: str,
    end_time: str,
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """按时间范围查询性能指标"""
    import main

    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)

    return main.db.get_metrics_by_time_range(start_dt, end_dt)
