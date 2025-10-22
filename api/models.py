"""API数据模型."""

from datetime import datetime

from pydantic import BaseModel, Field


class MonitoringDataResponse(BaseModel):
    """监控数据响应."""

    timestamp: datetime
    cpu_usage: float = Field(description="CPU使用率(%)")
    memory_usage: float = Field(description="内存使用率(%)")
    disk_io_read: float = Field(description="磁盘读取速率(bytes/s)")
    disk_io_write: float = Field(description="磁盘写入速率(bytes/s)")
    network_in: float = Field(description="网络接收速率(bytes/s)")
    network_out: float = Field(description="网络发送速率(bytes/s)")
    cpu_limit: float | None = Field(default=None, description="当前CPU限制(%)")
    is_peak: bool = Field(default=False, description="是否为峰值使用")


class CurrentStatusResponse(BaseModel):
    """当前状态响应."""

    cpu_usage: float
    memory_usage: float
    disk_io: dict[str, float]
    network: dict[str, float]
    window_12h_avg: float
    window_24h_peak: float
    current_limit: float
    quota_remaining: dict[str, float]


class ReservationCreate(BaseModel):
    """创建预留请求."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    start_time: datetime
    end_time: datetime
    cpu_quota: float = Field(ge=0, le=100)
    priority: int = Field(default=5, ge=1, le=10)


class ReservationResponse(BaseModel):
    """预留响应."""

    id: str
    name: str
    description: str | None
    start_time: datetime
    end_time: datetime
    cpu_quota: float
    priority: int
    enabled: bool


class ConfigUpdate(BaseModel):
    """配置更新请求."""

    key: str
    value: str


class SchedulerStatusResponse(BaseModel):
    """调度器状态响应."""

    running: bool
    current_cpu_limit: float
    avg_12h: float
    peak_24h: float
    data_points: int
    peak_count: int


class SystemInfoResponse(BaseModel):
    """系统信息响应."""

    cpu_count: int
    cpu_count_physical: int
    memory_total_gb: float
    disk_total_gb: float
    platform: str

