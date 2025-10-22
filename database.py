"""
数据库模型和连接管理
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

import bcrypt


class Database:
    """SQLite 数据库管理类"""

    def __init__(self, db_path: str = "scheduler.db"):
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def init_database(self):
        """初始化数据库表结构"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 性能指标历史数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    cpu_percent REAL NOT NULL,
                    memory_percent REAL NOT NULL,
                    memory_used_mb REAL NOT NULL,
                    memory_total_mb REAL NOT NULL,
                    disk_read_mb_per_sec REAL NOT NULL,
                    disk_write_mb_per_sec REAL NOT NULL,
                    network_sent_mb_per_sec REAL NOT NULL,
                    network_recv_mb_per_sec REAL NOT NULL
                )
            """)

            # 为 timestamp 创建索引以加速查询
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp
                ON metrics_history(timestamp)
            """)

            # 系统配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """)

            # 时间段负载配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS time_slot_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    max_load_percent REAL NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1
                )
            """)

            # 用户表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at DATETIME NOT NULL
                )
            """)

            # 插入默认配置
            self._insert_default_config(cursor)

            # 插入默认用户 (admin/admin123)
            self._insert_default_user(cursor)

    def _insert_default_config(self, cursor):
        """插入默认系统配置"""
        default_configs = {
            "min_load_percent": 10.0,
            "max_load_percent": 90.0,
            "rolling_window_hours": 24,
            "avg_load_limit_percent": 28.0,  # 默认28%,低于30%限制
            "history_retention_days": 30,
            "metrics_interval_seconds": 15,  # 默认15秒,提高采集精度
            "safety_factor": 0.85,  # 安全系数,留15%余量
            "startup_safety_factor": 0.7,  # 启动初期安全系数
            "startup_data_threshold_percent": 10.0,  # 启动数据阈值(占窗口的百分比)
        }

        for key, value in default_configs.items():
            cursor.execute(
                """
                INSERT OR IGNORE INTO system_config (key, value, updated_at)
                VALUES (?, ?, ?)
            """,
                (key, json.dumps(value), datetime.now().isoformat()),
            )

    def _insert_default_user(self, cursor):
        """插入默认管理员用户"""
        cursor.execute("SELECT COUNT(*) as count FROM users")
        if cursor.fetchone()["count"] == 0:
            password_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt())
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, created_at)
                VALUES (?, ?, ?)
            """,
                ("admin", password_hash.decode(), datetime.now().isoformat()),
            )

    # ==================== 性能指标相关方法 ====================

    def insert_metrics(self, metrics: dict[str, float]):
        """插入性能指标数据"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO metrics_history (
                    timestamp, cpu_percent, memory_percent, memory_used_mb,
                    memory_total_mb, disk_read_mb_per_sec, disk_write_mb_per_sec,
                    network_sent_mb_per_sec, network_recv_mb_per_sec
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    datetime.now().isoformat(),
                    metrics["cpu_percent"],
                    metrics["memory_percent"],
                    metrics["memory_used_mb"],
                    metrics["memory_total_mb"],
                    metrics["disk_read_mb_per_sec"],
                    metrics["disk_write_mb_per_sec"],
                    metrics["network_sent_mb_per_sec"],
                    metrics["network_recv_mb_per_sec"],
                ),
            )

    def get_metrics_in_window(self, hours: int) -> list[dict[str, Any]]:
        """获取指定时间窗口内的性能指标"""
        start_time = datetime.now() - timedelta(hours=hours)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM metrics_history
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
            """,
                (start_time.isoformat(),),
            )

            return [dict(row) for row in cursor.fetchall()]

    def get_latest_metrics(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取最新的 N 条性能指标"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM metrics_history
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def get_metrics_by_time_range(self, start_time: datetime, end_time: datetime) -> list[dict[str, Any]]:
        """按时间范围查询性能指标"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM metrics_history
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
            """,
                (start_time.isoformat(), end_time.isoformat()),
            )

            return [dict(row) for row in cursor.fetchall()]

    def cleanup_old_metrics(self, retention_days: int):
        """清理过期的性能指标数据"""
        cutoff_time = datetime.now() - timedelta(days=retention_days)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM metrics_history
                WHERE timestamp < ?
            """,
                (cutoff_time.isoformat(),),
            )

    # ==================== 配置相关方法 ====================

    def get_config(self, key: str) -> Any | None:
        """获取配置值"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT value FROM system_config WHERE key = ?
            """,
                (key,),
            )

            row = cursor.fetchone()
            return json.loads(row["value"]) if row else None

    def get_all_config(self) -> dict[str, Any]:
        """获取所有配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM system_config")

            return {row["key"]: json.loads(row["value"]) for row in cursor.fetchall()}

    def set_config(self, key: str, value: Any):
        """设置配置值"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO system_config (key, value, updated_at)
                VALUES (?, ?, ?)
            """,
                (key, json.dumps(value), datetime.now().isoformat()),
            )

    def update_config_batch(self, configs: dict[str, Any]):
        """批量更新配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for key, value in configs.items():
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO system_config (key, value, updated_at)
                    VALUES (?, ?, ?)
                """,
                    (key, json.dumps(value), datetime.now().isoformat()),
                )

    # ==================== 时间段配置相关方法 ====================

    def get_time_slots(self) -> list[dict[str, Any]]:
        """获取所有时间段配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM time_slot_config
                ORDER BY start_time ASC
            """)

            return [dict(row) for row in cursor.fetchall()]

    def add_time_slot(self, start_time: str, end_time: str, max_load_percent: float):
        """添加时间段配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO time_slot_config (start_time, end_time, max_load_percent, enabled)
                VALUES (?, ?, ?, 1)
            """,
                (start_time, end_time, max_load_percent),
            )

    def update_time_slot(self, slot_id: int, start_time: str, end_time: str, max_load_percent: float, enabled: bool):
        """更新时间段配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE time_slot_config
                SET start_time = ?, end_time = ?, max_load_percent = ?, enabled = ?
                WHERE id = ?
            """,
                (start_time, end_time, max_load_percent, 1 if enabled else 0, slot_id),
            )

    def delete_time_slot(self, slot_id: int):
        """删除时间段配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM time_slot_config WHERE id = ?", (slot_id,))

    # ==================== 用户认证相关方法 ====================

    def verify_user(self, username: str, password: str) -> bool:
        """验证用户凭据"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT password_hash FROM users WHERE username = ?
            """,
                (username,),
            )

            row = cursor.fetchone()
            if not row:
                return False

            return bcrypt.checkpw(password.encode(), row["password_hash"].encode())

    def get_user(self, username: str) -> dict[str, Any] | None:
        """获取用户信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, username, created_at FROM users WHERE username = ?
            """,
                (username,),
            )

            row = cursor.fetchone()
            return dict(row) if row else None
