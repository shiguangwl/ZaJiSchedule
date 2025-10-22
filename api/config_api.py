"""
配置管理相关 API
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user

router = APIRouter(prefix="/api/config", tags=["配置管理"])


class SystemConfigUpdate(BaseModel):
    min_load_percent: float
    max_load_percent: float
    rolling_window_hours: int
    avg_load_limit_percent: float
    history_retention_days: int
    metrics_interval_seconds: int
    safety_factor: float
    startup_safety_factor: float
    startup_data_threshold_percent: float


class TimeSlotCreate(BaseModel):
    start_time: str
    end_time: str
    max_load_percent: float


class TimeSlotUpdate(BaseModel):
    start_time: str
    end_time: str
    max_load_percent: float
    enabled: bool


@router.get("/system")
async def get_system_config(
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """获取系统配置"""
    from main import config

    return config.get_all()


@router.put("/system")
async def update_system_config(
    config_update: SystemConfigUpdate,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """更新系统配置"""
    from main import config

    # 验证配置值
    if config_update.min_load_percent < 0 or config_update.min_load_percent > 100:
        raise HTTPException(status_code=400, detail="min_load_percent 必须在 0-100 之间")

    if config_update.max_load_percent < 0 or config_update.max_load_percent > 100:
        raise HTTPException(status_code=400, detail="max_load_percent 必须在 0-100 之间")

    if config_update.min_load_percent > config_update.max_load_percent:
        raise HTTPException(status_code=400, detail="min_load_percent 不能大于 max_load_percent")

    if config_update.rolling_window_hours < 1:
        raise HTTPException(status_code=400, detail="rolling_window_hours 必须大于 0")

    if config_update.avg_load_limit_percent < 0 or config_update.avg_load_limit_percent > 100:
        raise HTTPException(status_code=400, detail="avg_load_limit_percent 必须在 0-100 之间")

    if config_update.safety_factor < 0.5 or config_update.safety_factor > 1.0:
        raise HTTPException(status_code=400, detail="safety_factor 必须在 0.5-1.0 之间")

    if config_update.startup_safety_factor < 0.5 or config_update.startup_safety_factor > 1.0:
        raise HTTPException(status_code=400, detail="startup_safety_factor 必须在 0.5-1.0 之间")

    if config_update.startup_data_threshold_percent < 1 or config_update.startup_data_threshold_percent > 50:
        raise HTTPException(status_code=400, detail="startup_data_threshold_percent 必须在 1-50 之间")

    # 更新配置
    config.update_batch(config_update.dict())

    return {"message": "配置更新成功"}


@router.get("/timeslots")
async def get_time_slots(
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """获取所有时间段配置"""
    from main import db

    return db.get_time_slots()


@router.post("/timeslots")
async def create_time_slot(
    time_slot: TimeSlotCreate,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """创建时间段配置"""
    from main import db

    # 验证时间格式
    try:
        from datetime import datetime

        datetime.strptime(time_slot.start_time, "%H:%M")
        datetime.strptime(time_slot.end_time, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="时间格式错误,应为 HH:MM")

    if time_slot.max_load_percent < 0 or time_slot.max_load_percent > 100:
        raise HTTPException(status_code=400, detail="max_load_percent 必须在 0-100 之间")

    db.add_time_slot(
        time_slot.start_time,
        time_slot.end_time,
        time_slot.max_load_percent,
    )

    return {"message": "时间段配置创建成功"}


@router.put("/timeslots/{slot_id}")
async def update_time_slot(
    slot_id: int,
    time_slot: TimeSlotUpdate,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """更新时间段配置"""
    from main import db

    # 验证时间格式
    try:
        from datetime import datetime

        datetime.strptime(time_slot.start_time, "%H:%M")
        datetime.strptime(time_slot.end_time, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="时间格式错误,应为 HH:MM")

    if time_slot.max_load_percent < 0 or time_slot.max_load_percent > 100:
        raise HTTPException(status_code=400, detail="max_load_percent 必须在 0-100 之间")

    db.update_time_slot(
        slot_id,
        time_slot.start_time,
        time_slot.end_time,
        time_slot.max_load_percent,
        time_slot.enabled,
    )

    return {"message": "时间段配置更新成功"}


@router.delete("/timeslots/{slot_id}")
async def delete_time_slot(
    slot_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """删除时间段配置"""
    from main import db

    db.delete_time_slot(slot_id)
    return {"message": "时间段配置删除成功"}
