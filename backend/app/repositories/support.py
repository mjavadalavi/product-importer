"""
Repository for SupportTicket CRUD and domain-specific queries.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.support_ticket import SupportTicket, TicketStatus
from app.repositories.base import BaseRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SupportTicketRepository(BaseRepository[SupportTicket]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SupportTicket, session)

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SupportTicket], int]:
        """Return (rows ordered by created_at DESC, total) for the given user."""
        base_where = SupportTicket.user_id == user_id

        count_query = select(func.count()).select_from(SupportTicket).where(base_where)
        count_result = await self.session.execute(count_query)
        total: int = count_result.scalar() or 0

        offset = (page - 1) * page_size
        rows_query = (
            select(SupportTicket)
            .where(base_where)
            .order_by(SupportTicket.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows_result = await self.session.execute(rows_query)
        rows = list(rows_result.scalars().all())

        logger.debug(
            "list_for_user user_id=%s page=%s page_size=%s total=%s returned=%s",
            user_id, page, page_size, total, len(rows),
        )
        return rows, total

    async def create_for_user(
        self,
        *,
        user_id: UUID,
        subject: str,
        body: str,
    ) -> SupportTicket:
        """Create a ticket with status=OPEN. Calls db.flush() (no commit)."""
        ticket = SupportTicket(
            user_id=user_id,
            subject=subject,
            body=body,
            status=TicketStatus.OPEN,
        )
        self.session.add(ticket)
        await self.session.flush()
        await self.session.refresh(ticket)
        logger.info(
            "Created SupportTicket id=%s user_id=%s subject=%r",
            ticket.id, user_id, subject,
        )
        return ticket
