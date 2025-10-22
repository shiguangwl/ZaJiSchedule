"""配额预留管理模块."""

import uuid
from datetime import UTC, datetime
from typing import NamedTuple

from config.database import get_db
from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


class Reservation(NamedTuple):
    """配额预留."""

    id: str
    name: str
    description: str | None
    start_time: datetime
    end_time: datetime
    cpu_quota: float
    priority: int
    enabled: bool


class QuotaManager:
    """配额预留管理器."""

    def __init__(self) -> None:
        """初始化配额管理器."""
        self.settings = get_settings()
        self.db = get_db()
        logger.info("初始化配额管理器")

    async def create_reservation(
        self,
        name: str,
        start_time: datetime,
        end_time: datetime,
        cpu_quota: float,
        description: str | None = None,
        priority: int = 5,
    ) -> str | None:
        """创建配额预留.

        Args:
            name: 预留名称
            start_time: 开始时间
            end_time: 结束时间
            cpu_quota: 预留CPU配额(%)
            description: 描述
            priority: 优先级(1-10)

        Returns:
            预留ID,如果创建失败则返回None
        """
        # 验证参数
        if start_time >= end_time:
            logger.error("开始时间必须早于结束时间")
            return None

        duration_minutes = (end_time - start_time).total_seconds() / 60
        if duration_minutes < self.settings.reservation_min_duration:
            logger.error("预留时长不能少于%d分钟", self.settings.reservation_min_duration)
            return None

        duration_hours = duration_minutes / 60
        if duration_hours > self.settings.reservation_max_duration:
            logger.error("预留时长不能超过%d小时", self.settings.reservation_max_duration)
            return None

        if cpu_quota < 0 or cpu_quota > 100:
            logger.error("CPU配额必须在0-100之间")
            return None

        # 检查冲突
        if await self._check_conflict(start_time, end_time):
            logger.error("预留时间段与现有预留冲突")
            return None

        # 创建预留
        reservation_id = str(uuid.uuid4())
        try:
            async with self.db.get_async_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO quota_reservations
                    (id, name, description, start_time, end_time, cpu_quota, priority, enabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        reservation_id,
                        name,
                        description,
                        start_time.isoformat(),
                        end_time.isoformat(),
                        cpu_quota,
                        priority,
                    ),
                )
                await conn.commit()

            logger.info(
                "创建配额预留: id=%s, name=%s, start=%s, end=%s, quota=%.1f%%",
                reservation_id,
                name,
                start_time,
                end_time,
                cpu_quota,
            )
            return reservation_id

        except Exception:
            logger.exception("创建配额预留失败")
            return None

    async def _check_conflict(
        self,
        start_time: datetime,
        end_time: datetime,
        exclude_id: str | None = None,
    ) -> bool:
        """检查时间段是否与现有预留冲突.

        Args:
            start_time: 开始时间
            end_time: 结束时间
            exclude_id: 排除的预留ID(用于更新时)

        Returns:
            是否存在冲突
        """
        try:
            async with self.db.get_async_connection() as conn:
                query = """
                    SELECT COUNT(*) as count FROM quota_reservations
                    WHERE enabled = 1
                    AND (
                        (start_time <= ? AND end_time >= ?)
                        OR (start_time <= ? AND end_time >= ?)
                        OR (start_time >= ? AND end_time <= ?)
                    )
                """
                params = [
                    start_time.isoformat(),
                    start_time.isoformat(),
                    end_time.isoformat(),
                    end_time.isoformat(),
                    start_time.isoformat(),
                    end_time.isoformat(),
                ]

                if exclude_id:
                    query += " AND id != ?"
                    params.append(exclude_id)

                async with conn.execute(query, params) as cursor:
                    row = await cursor.fetchone()
                    return row["count"] > 0 if row else False

        except Exception:
            logger.exception("检查预留冲突失败")
            return True  # 出错时保守处理,认为有冲突

    async def get_active_reservation(
        self,
        current_time: datetime | None = None,
    ) -> Reservation | None:
        """获取当前生效的预留.

        Args:
            current_time: 当前时间,默认为系统时间

        Returns:
            当前生效的预留,如果没有则返回None
        """
        if current_time is None:
            current_time = datetime.now(UTC)

        try:
            async with (
                self.db.get_async_connection() as conn,
                conn.execute(
                    """
                    SELECT id, name, description, start_time, end_time,
                           cpu_quota, priority, enabled
                    FROM quota_reservations
                    WHERE enabled = 1
                    AND start_time <= ?
                    AND end_time >= ?
                    ORDER BY priority DESC, start_time ASC
                    LIMIT 1
                    """,
                    (current_time.isoformat(), current_time.isoformat()),
                ) as cursor,
            ):
                row = await cursor.fetchone()
                if row:
                    return Reservation(
                        id=row["id"],
                        name=row["name"],
                        description=row["description"],
                        start_time=datetime.fromisoformat(row["start_time"]),
                        end_time=datetime.fromisoformat(row["end_time"]),
                        cpu_quota=row["cpu_quota"],
                        priority=row["priority"],
                        enabled=bool(row["enabled"]),
                    )
                return None

        except Exception:
            logger.exception("获取当前预留失败")
            return None

    async def get_all_reservations(self) -> list[Reservation]:
        """获取所有预留.

        Returns:
            预留列表
        """
        try:
            async with (
                self.db.get_async_connection() as conn,
                conn.execute(
                    """
                    SELECT id, name, description, start_time, end_time,
                           cpu_quota, priority, enabled
                    FROM quota_reservations
                    ORDER BY start_time DESC
                    """,
                ) as cursor,
            ):
                rows = await cursor.fetchall()
                return [
                    Reservation(
                        id=row["id"],
                        name=row["name"],
                        description=row["description"],
                        start_time=datetime.fromisoformat(row["start_time"]),
                        end_time=datetime.fromisoformat(row["end_time"]),
                        cpu_quota=row["cpu_quota"],
                        priority=row["priority"],
                        enabled=bool(row["enabled"]),
                    )
                    for row in rows
                ]

        except Exception:
            logger.exception("获取所有预留失败")
            return []

    async def delete_reservation(self, reservation_id: str) -> bool:
        """删除预留.

        Args:
            reservation_id: 预留ID

        Returns:
            是否成功删除
        """
        try:
            async with self.db.get_async_connection() as conn:
                await conn.execute(
                    "DELETE FROM quota_reservations WHERE id = ?",
                    (reservation_id,),
                )
                await conn.commit()

            logger.info("删除配额预留: id=%s", reservation_id)
            return True

        except Exception:
            logger.exception("删除配额预留失败")
            return False
