"""数据库连接管理."""

import sqlite3
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager

import aiosqlite

from config.settings import get_settings


class Database:
    """数据库管理类."""

    def __init__(self) -> None:
        """初始化数据库管理器."""
        self.settings = get_settings()
        self.db_path = self.settings.get_database_path()
        self._initialized = False

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """获取同步数据库连接(上下文管理器)."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @asynccontextmanager
    async def get_async_connection(
        self,
    ) -> AsyncGenerator[aiosqlite.Connection, None]:
        """获取异步数据库连接(上下文管理器)."""
        conn = await aiosqlite.connect(str(self.db_path))
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        finally:
            await conn.close()

    def initialize_database(self) -> None:
        """初始化数据库表结构."""
        if self._initialized:
            return

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. 配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    value_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT,
                    min_value TEXT,
                    max_value TEXT,
                    default_value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_by TEXT
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_config_category ON config(category)",
            )

            # 2. 监控数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS monitoring_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cpu_usage REAL NOT NULL,
                    memory_usage REAL NOT NULL,
                    disk_io_read REAL NOT NULL,
                    disk_io_write REAL NOT NULL,
                    network_in REAL NOT NULL,
                    network_out REAL NOT NULL,
                    cpu_limit REAL,
                    is_peak BOOLEAN DEFAULT 0
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_monitoring_timestamp "
                "ON monitoring_data(timestamp)",
            )

            # 3. 配额预留表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quota_reservations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP NOT NULL,
                    cpu_quota REAL NOT NULL,
                    priority INTEGER DEFAULT 5,
                    enabled BOOLEAN DEFAULT 1,
                    recurrence TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    updated_at TIMESTAMP
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_reservation_time "
                "ON quota_reservations(start_time, end_time)",
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_reservation_enabled "
                "ON quota_reservations(enabled)",
            )

            # 4. 调度日志表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedule_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cpu_limit REAL,
                    avg_12h REAL,
                    avg_quota_remaining REAL,
                    peak_24h REAL,
                    peak_quota_remaining REAL,
                    available_quota REAL,
                    reservation_id TEXT,
                    action TEXT NOT NULL,
                    reason TEXT,
                    scheduler_mode TEXT
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_schedule_timestamp "
                "ON schedule_logs(timestamp)",
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_schedule_reservation "
                "ON schedule_logs(reservation_id)",
            )

            # 5. 配置历史表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    changed_by TEXT,
                    reason TEXT
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_config_history_key "
                "ON config_history(config_key)",
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_config_history_time "
                "ON config_history(changed_at)",
            )

            # 6. 告警记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details TEXT,
                    acknowledged BOOLEAN DEFAULT 0,
                    acknowledged_at TIMESTAMP,
                    acknowledged_by TEXT,
                    resolved BOOLEAN DEFAULT 0,
                    resolved_at TIMESTAMP
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)",
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type)",
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity)",
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged "
                "ON alerts(acknowledged)",
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved)",
            )

            conn.commit()
            self._initialized = True

    async def cleanup_old_data(self) -> None:
        """清理过期数据."""
        retention_days = self.settings.database_retention_days
        async with self.get_async_connection() as conn:
            # 清理监控数据
            await conn.execute(
                """
                DELETE FROM monitoring_data
                WHERE timestamp < datetime('now', '-' || ? || ' days')
                """,
                (retention_days,),
            )
            # 清理调度日志
            await conn.execute(
                """
                DELETE FROM schedule_logs
                WHERE timestamp < datetime('now', '-' || ? || ' days')
                """,
                (retention_days,),
            )
            # 清理已解决的告警
            await conn.execute(
                """
                DELETE FROM alerts
                WHERE resolved = 1
                AND resolved_at < datetime('now', '-' || ? || ' days')
                """,
                (retention_days,),
            )
            await conn.commit()


_db_instance: Database | None = None


def get_db() -> Database:
    """获取数据库实例(单例)."""
    global _db_instance  # noqa: PLW0603
    if _db_instance is None:
        _db_instance = Database()
        _db_instance.initialize_database()
    return _db_instance
