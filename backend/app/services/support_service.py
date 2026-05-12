"""
Service layer for support-ticket operations.

Owns the transaction boundary: the repository flushes but does not commit;
this service commits and refreshes after each write.
"""
from __future__ import annotations

import math
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.support_ticket import SupportTicket
from app.repositories.support import SupportTicketRepository
from app.schemas.common import PaginatedResponse
from app.schemas.support import SupportTicketCreate, SupportTicketOut
from app.utils.logging import LoggerMixin


class SupportService(LoggerMixin):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SupportTicketRepository(session)

    async def create(
        self,
        user_id: UUID,
        request: SupportTicketCreate,
    ) -> SupportTicket:
        """Create a support ticket and persist it.

        Trims leading/trailing whitespace from subject and body before
        writing. The repository flushes the row; this method commits and
        refreshes so the returned ORM object reflects all DB-generated
        values (id, created_at, updated_at).
        """
        subject = request.subject.strip()
        body = request.body.strip()

        self.logger.info(
            "SupportService.create user_id=%s subject_len=%s",
            user_id,
            len(subject),
        )

        ticket = await self.repo.create_for_user(
            user_id=user_id,
            subject=subject,
            body=body,
        )

        await self.session.commit()
        await self.session.refresh(ticket)

        self.logger.info(
            "SupportService.create done ticket_id=%s user_id=%s",
            ticket.id,
            user_id,
        )
        return ticket

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[SupportTicketOut]:
        """Return a paginated list of tickets belonging to *user_id*.

        Delegates the query to the repository and maps each ORM row to
        a SupportTicketOut DTO before wrapping in PaginatedResponse.
        When total == 0 the build() classmethod returns total_pages=0
        which would make has_more False and page=1 still valid, so no
        special-casing is needed here beyond what build() already does.
        """
        self.logger.info(
            "SupportService.list_for_user user_id=%s page=%s page_size=%s",
            user_id,
            page,
            page_size,
        )

        rows, total = await self.repo.list_for_user(
            user_id,
            page=page,
            page_size=page_size,
        )

        items = [SupportTicketOut.model_validate(row) for row in rows]

        # Compute total_pages: at least 1 so that page=1 is always valid.
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        self.logger.debug(
            "SupportService.list_for_user user_id=%s total=%s total_pages=%s returned=%s",
            user_id,
            total,
            total_pages,
            len(items),
        )

        return PaginatedResponse[SupportTicketOut](
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_more=page < total_pages,
        )
