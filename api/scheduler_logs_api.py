"""
调度记录相关 API
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from auth import get_current_user

router = APIRouter(prefix="/api/scheduler-logs", tags=["调度记录"])


@router.get("")
async def get_scheduler_logs(
    log_type: str | None = Query(None, description="日志类型: system, cpu_limit_adjust, alert, process_sync, error"),
    level: str | None = Query(None, description="日志级别: info, warning, error"),
    hours: int = Query(24, description="查询最近N小时的记录"),
    limit: int = Query(1000, description="最多返回记录数"),
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """获取调度记录"""
    import sys

    main_module = sys.modules["__main__"]

    return main_module.db.get_scheduler_logs(
        log_type=log_type,
        level=level,
        hours=hours,
        limit=limit,
    )


@router.get("/range")
async def get_scheduler_logs_by_range(
    start_time: str = Query(..., description="开始时间 (ISO格式)"),
    end_time: str = Query(..., description="结束时间 (ISO格式)"),
    log_type: str | None = Query(None, description="日志类型"),
    level: str | None = Query(None, description="日志级别"),
    limit: int = Query(1000, description="最多返回记录数"),
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """按时间范围查询调度记录"""
    import sys

    main_module = sys.modules["__main__"]

    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)

    return main_module.db.get_scheduler_logs_by_range(
        start_time=start_dt,
        end_time=end_dt,
        log_type=log_type,
        level=level,
        limit=limit,
    )


@router.get("/stats")
async def get_scheduler_logs_stats(
    hours: int = Query(24, description="统计最近N小时的记录"),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """获取调度记录统计信息"""
    import sys

    main_module = sys.modules["__main__"]

    logs = main_module.db.get_scheduler_logs(hours=hours, limit=10000)

    # 统计各类型数量
    type_counts = {}
    level_counts = {}
    cpu_limit_adjustments = []

    for log in logs:
        # 统计类型
        log_type = log["log_type"]
        type_counts[log_type] = type_counts.get(log_type, 0) + 1

        # 统计级别
        level = log["level"]
        level_counts[level] = level_counts.get(level, 0) + 1

        # 收集CPU限制调整记录
        if log_type == "cpu_limit_adjust" and log["cpu_limit_before"] and log["cpu_limit_after"]:
            cpu_limit_adjustments.append(
                {
                    "timestamp": log["timestamp"],
                    "from": log["cpu_limit_before"],
                    "to": log["cpu_limit_after"],
                    "change": log["cpu_limit_after"] - log["cpu_limit_before"],
                },
            )

    return {
        "total_logs": len(logs),
        "type_counts": type_counts,
        "level_counts": level_counts,
        "cpu_limit_adjustments": cpu_limit_adjustments[:50],  # 最近50次调整
        "alert_count": type_counts.get("alert", 0),
        "error_count": type_counts.get("error", 0),
    }
