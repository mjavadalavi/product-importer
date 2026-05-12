"""Repository for File CRUD and domain-specific queries."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.file import File, FileStatus
from app.repositories.base import BaseRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class FileRepository(BaseRepository[File]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(File, session)

    async def get_for_user(self, file_id: UUID, user_id: UUID) -> File | None:
        """Return the File owned by ``user_id`` with the given ``file_id``, or None.

        Excludes soft-deleted (status=DELETED) records.
        """
        query = (
            select(File)
            .where(
                and_(
                    File.id == file_id,
                    File.user_id == user_id,
                    File.status != FileStatus.DELETED,
                )
            )
        )
        result = await self.session.execute(query)
        row = result.scalar_one_or_none()
        logger.debug(
            "get_for_user file_id=%s user_id=%s found=%s",
            file_id, user_id, row is not None,
        )
        return row

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        kind: str | None = None,
        target_type: str | None = None,
        target_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[File], int]:
        """Return (rows ordered by created_at DESC, total) for the given user.

        All active (non-DELETED) files are returned.  Optional filters narrow
        the result set by ``kind``, ``target_type``, and/or ``target_id``.
        """
        base_conditions = [
            File.user_id == user_id,
            File.status != FileStatus.DELETED,
        ]
        if kind is not None:
            base_conditions.append(File.kind == kind)
        if target_type is not None:
            base_conditions.append(File.target_type == target_type)
        if target_id is not None:
            base_conditions.append(File.target_id == target_id)

        where_clause = and_(*base_conditions)

        count_query = select(func.count()).select_from(File).where(where_clause)
        count_result = await self.session.execute(count_query)
        total: int = count_result.scalar() or 0

        offset = (page - 1) * page_size
        rows_query = (
            select(File)
            .where(where_clause)
            .order_by(File.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows_result = await self.session.execute(rows_query)
        rows = list(rows_result.scalars().all())

        logger.debug(
            "list_for_user user_id=%s kind=%s target_type=%s target_id=%s "
            "page=%s page_size=%s total=%s returned=%s",
            user_id, kind, target_type, target_id, page, page_size, total, len(rows),
        )
        return rows, total

    async def find_by_target(
        self,
        target_type: str,
        target_id: UUID,
    ) -> list[File]:
        """Return all active files bound to a specific domain resource."""
        query = (
            select(File)
            .where(
                and_(
                    File.target_type == target_type,
                    File.target_id == target_id,
                    File.status != FileStatus.DELETED,
                )
            )
            .order_by(File.created_at.asc())
        )
        result = await self.session.execute(query)
        rows = list(result.scalars().all())
        logger.debug(
            "find_by_target target_type=%s target_id=%s count=%s",
            target_type, target_id, len(rows),
        )
        return rows

    async def mark_deleted(self, file_id: UUID) -> None:
        """Set status=DELETED on the given file row (soft delete)."""
        file = await self.get(id=file_id)
        if file is None:
            logger.warning("mark_deleted: file_id=%s not found", file_id)
            return
        file.status = FileStatus.DELETED
        self.session.add(file)
        await self.session.flush()
        logger.info("mark_deleted file_id=%s", file_id)
