"""系统配置管理."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """系统配置类."""

    model_config = SettingsConfigDict(
        env_prefix="CPU_SCHEDULER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 服务器配置
    server_host: str = Field(default="0.0.0.0", description="服务监听地址")  # noqa: S104
    server_port: int = Field(default=8080, description="服务监听端口")
    server_debug: bool = Field(default=False, description="调试模式")
    server_workers: int = Field(default=1, description="工作进程数")

    # WebSocket配置
    ws_enabled: bool = Field(default=True, description="启用WebSocket")
    ws_push_interval: int = Field(default=1, description="WebSocket推送间隔(秒)")
    ws_max_connections: int = Field(default=100, description="最大WebSocket连接数")

    # 数据库配置
    database_path: str = Field(
        default="data/cpu_scheduler.db",
        description="数据库文件路径",
    )
    database_retention_days: int = Field(default=30, description="数据保留天数")
    database_sampling_interval: int = Field(default=1, description="数据采样间隔(秒)")
    database_batch_size: int = Field(default=100, description="批量插入大小")
    database_batch_interval: int = Field(default=10, description="批量插入间隔(秒)")

    # 监控配置
    monitoring_interval: int = Field(default=1, description="监控采集间隔(秒)")
    monitoring_enable_cpu: bool = Field(default=True, description="启用CPU监控")
    monitoring_enable_memory: bool = Field(default=True, description="启用内存监控")
    monitoring_enable_disk: bool = Field(default=True, description="启用磁盘IO监控")
    monitoring_enable_network: bool = Field(default=True, description="启用网络监控")
    monitoring_smooth_window: int = Field(default=5, description="数据平滑窗口大小(秒)")

    # CPU限制配置 - 平均限制
    limits_avg_window_hours: int = Field(default=12, description="平均窗口长度(小时)")
    limits_avg_max_usage: float = Field(default=30.0, description="平均最大CPU占用(%)")
    limits_avg_min_usage: float = Field(default=5.0, description="平均最低CPU占用(%)")
    limits_avg_warning_threshold: float = Field(
        default=5.0,
        description="平均配额警告阈值(%)",
    )
    limits_avg_critical_threshold: float = Field(
        default=2.0,
        description="平均配额严重阈值(%)",
    )

    # CPU限制配置 - 峰值限制
    limits_peak_window_hours: int = Field(default=24, description="峰值窗口长度(小时)")
    limits_peak_threshold: float = Field(default=95.0, description="峰值CPU阈值(%)")
    limits_peak_max_duration: int = Field(
        default=600,
        description="峰值最大持续时间(秒)",
    )
    limits_peak_warning_threshold: int = Field(
        default=120,
        description="峰值配额警告阈值(秒)",
    )
    limits_peak_critical_threshold: int = Field(
        default=60,
        description="峰值配额严重阈值(秒)",
    )

    # CPU限制配置 - 安全边界
    limits_absolute_min_cpu: float = Field(default=5.0, description="绝对最小CPU限制(%)")
    limits_absolute_max_cpu: float = Field(default=95.0, description="绝对最大CPU限制(%)")
    limits_safety_margin: float = Field(default=5.0, description="安全余量(%)")

    # 调度器配置
    scheduler_mode: Literal["conservative", "balanced", "aggressive"] = Field(
        default="balanced",
        description="调度模式",
    )
    scheduler_enabled: bool = Field(default=True, description="启用调度器")
    scheduler_adjustment_step: float = Field(default=5.0, description="CPU限制调整步长(%)")
    scheduler_adjustment_interval: int = Field(
        default=10,
        description="调整最小间隔(秒)",
    )
    scheduler_smooth_factor: float = Field(default=0.3, description="调整平滑系数(0-1)")
    scheduler_change_threshold: float = Field(
        default=2.0,
        description="触发调整的最小变化(%)",
    )

    # 调度器配置 - 配额充足时
    scheduler_quota_high_cpu_limit: float = Field(
        default=85.0,
        description="配额充足时CPU限制(%)",
    )
    scheduler_quota_high_adjustment_speed: float = Field(
        default=1.0,
        description="配额充足时调整速度",
    )

    # 调度器配置 - 配额紧张时
    scheduler_quota_medium_cpu_limit: float = Field(
        default=60.0,
        description="配额紧张时CPU限制(%)",
    )
    scheduler_quota_medium_adjustment_speed: float = Field(
        default=0.7,
        description="配额紧张时调整速度",
    )

    # 调度器配置 - 配额即将耗尽时
    scheduler_quota_low_cpu_limit: float = Field(
        default=35.0,
        description="配额即将耗尽时CPU限制(%)",
    )
    scheduler_quota_low_adjustment_speed: float = Field(
        default=0.5,
        description="配额即将耗尽时调整速度",
    )

    # 调度器配置 - 紧急模式
    scheduler_emergency_threshold: float = Field(
        default=1.0,
        description="紧急模式阈值(%)",
    )
    scheduler_emergency_cpu_limit: float = Field(
        default=20.0,
        description="紧急模式CPU限制(%)",
    )

    # 预留管理配置
    reservation_enabled: bool = Field(default=True, description="启用预留功能")
    reservation_max_concurrent: int = Field(default=10, description="最大并发预留数")
    reservation_min_duration: int = Field(default=5, description="最小预留时长(分钟)")
    reservation_max_duration: int = Field(default=24, description="最大预留时长(小时)")

    # 告警配置
    alerts_enabled: bool = Field(default=True, description="启用告警")
    alerts_quota_alert_enabled: bool = Field(default=True, description="配额告警")
    alerts_system_alert_enabled: bool = Field(default=True, description="系统告警")
    alerts_cpu_high_threshold: float = Field(default=90.0, description="CPU高使用率阈值(%)")
    alerts_cpu_high_duration: int = Field(default=300, description="持续时间(秒)")
    alerts_memory_high_threshold: float = Field(
        default=85.0,
        description="内存高使用率阈值(%)",
    )

    # 性能配置
    performance_max_memory_mb: int = Field(default=512, description="最大内存使用(MB)")
    performance_max_cpu_percent: float = Field(
        default=5.0,
        description="监控程序自身CPU限制(%)",
    )
    performance_cache_enabled: bool = Field(default=True, description="启用缓存")
    performance_cache_ttl: int = Field(default=60, description="缓存TTL(秒)")

    # cgroup配置
    cgroup_path: str = Field(
        default="/sys/fs/cgroup/cpu_scheduler",
        description="cgroup路径",
    )
    cgroup_enabled: bool = Field(default=True, description="启用cgroup控制")

    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")
    log_file: str = Field(default="logs/cpu_scheduler.log", description="日志文件路径")
    log_max_bytes: int = Field(default=10485760, description="日志文件最大大小(字节)")
    log_backup_count: int = Field(default=5, description="日志备份数量")

    def get_database_path(self) -> Path:
        """获取数据库文件的绝对路径."""
        db_path = Path(self.database_path)
        if not db_path.is_absolute():
            # 相对于项目根目录
            project_root = Path(__file__).parent.parent.parent
            db_path = project_root / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    def get_log_path(self) -> Path:
        """获取日志文件的绝对路径."""
        log_path = Path(self.log_file)
        if not log_path.is_absolute():
            project_root = Path(__file__).parent.parent.parent
            log_path = project_root / log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        return log_path


@lru_cache
def get_settings() -> Settings:
    """获取配置单例."""
    return Settings()
