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

            # 调度记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduler_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    log_type TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details TEXT,
                    cpu_limit_before REAL,
                    cpu_limit_after REAL,
                    current_cpu REAL,
                    avg_cpu REAL,
                    safe_limit REAL
                )
            """)

            # 为 timestamp 和 log_type 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scheduler_logs_timestamp
                ON scheduler_logs(timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scheduler_logs_type
                ON scheduler_logs(log_type)
            """)

            # 迁移/升级 schema（添加缺失列等）
            self._migrate_schema(cursor)

            # 插入默认配置
            self._insert_default_config(cursor)

            # 插入默认用户 (admin/admin123)
            self._insert_default_user(cursor)

    def _migrate_schema(self, cursor):
        """迁移/升级数据库 schema（幂等）"""
        try:
            # 检查 metrics_history 是否存在 applied_cpu_limit 列
            cursor.execute("PRAGMA table_info(metrics_history)")
            columns = [row[1] for row in cursor.fetchall()]
            if "applied_cpu_limit" not in columns:
                cursor.execute("ALTER TABLE metrics_history ADD COLUMN applied_cpu_limit REAL")
        except Exception:
            # 旧版SQLite或其他问题时不中断主流程
            pass

    def _insert_default_config(self, cursor):
        """插入默认系统配置"""
        default_configs = {
            "min_load_percent": 10.0,  # 最低负载
            "max_load_percent": 90.0,  # 最高负载
            "rolling_window_hours": 24,  # 滑动窗口
            "avg_load_limit_percent": 30.0,  # 平均负载限制
            "history_retention_days": 30,  # 历史数据保留天数
            "metrics_interval_seconds": 5,  # 默认5秒,提高采集精度（按确认）
            "cpu_limit_adjust_interval_seconds": 15,  # CPU限制调整间隔(秒),独立于采集频率
            "process_sync_interval_seconds": 60,  # 全量进程同步间隔(秒)
            "safety_factor": 0.9,  # 安全系数,更积极利用配额（按确认）
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

    def insert_metrics(self, metrics: dict[str, float | None]):
        """插入性能指标数据"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO metrics_history (
                    timestamp, cpu_percent, memory_percent, memory_used_mb,
                    memory_total_mb, disk_read_mb_per_sec, disk_write_mb_per_sec,
                    network_sent_mb_per_sec, network_recv_mb_per_sec, applied_cpu_limit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    metrics.get("applied_cpu_limit"),
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

    def update_user_password(self, username: str, new_password: str) -> bool:
        """
        更新用户密码

        Args:
            username: 用户名
            new_password: 新密码(明文)

        Returns:
            是否更新成功
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 检查用户是否存在
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if not cursor.fetchone():
                return False

            # 生成新的密码哈希
            password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())

            # 更新密码
            cursor.execute(
                """
                UPDATE users
                SET password_hash = ?
                WHERE username = ?
            """,
                (password_hash.decode(), username),
            )

            return cursor.rowcount > 0

    # ==================== 调度记录相关方法 ====================

    def insert_scheduler_log(
        self,
        log_type: str,
        level: str,
        message: str,
        details: dict[str, Any] | None = None,
        cpu_limit_before: float | None = None,
        cpu_limit_after: float | None = None,
        current_cpu: float | None = None,
        avg_cpu: float | None = None,
        safe_limit: float | None = None,
    ):
        """插入调度记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO scheduler_logs (
                    timestamp, log_type, level, message, details,
                    cpu_limit_before, cpu_limit_after, current_cpu, avg_cpu, safe_limit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    datetime.now().isoformat(),
                    log_type,
                    level,
                    message,
                    json.dumps(details) if details else None,
                    cpu_limit_before,
                    cpu_limit_after,
                    current_cpu,
                    avg_cpu,
                    safe_limit,
                ),
            )

    def get_scheduler_logs(
        self,
        log_type: str | None = None,
        level: str | None = None,
        hours: int = 24,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """获取调度记录"""
        start_time = datetime.now() - timedelta(hours=hours)

        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT * FROM scheduler_logs
                WHERE timestamp >= ?
            """
            params = [start_time.isoformat()]

            if log_type:
                query += " AND log_type = ?"
                params.append(log_type)

            if level:
                query += " AND level = ?"
                params.append(level)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(str(limit))

            cursor.execute(query, params)

            logs = []
            for row in cursor.fetchall():
                log = dict(row)
                if log["details"]:
                    log["details"] = json.loads(log["details"])
                logs.append(log)

            return logs

    def get_scheduler_logs_by_range(
        self,
        start_time: datetime,
        end_time: datetime,
        log_type: str | None = None,
        level: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """按时间范围查询调度记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT * FROM scheduler_logs
                WHERE timestamp BETWEEN ? AND ?
            """
            params = [start_time.isoformat(), end_time.isoformat()]

            if log_type:
                query += " AND log_type = ?"
                params.append(log_type)

            if level:
                query += " AND level = ?"
                params.append(level)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(str(limit))

            cursor.execute(query, params)

            logs = []
            for row in cursor.fetchall():
                log = dict(row)
                if log["details"]:
                    log["details"] = json.loads(log["details"])
                logs.append(log)

            return logs

    def cleanup_old_scheduler_logs(self, retention_days: int):
        """清理过期的调度记录"""
        cutoff_time = datetime.now() - timedelta(days=retention_days)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM scheduler_logs
                WHERE timestamp < ?
            """,
                (cutoff_time.isoformat(),),
            )
