from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db.models.support_ticket import SupportTicket, TicketStatus
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.support import SupportTicketCreate, SupportTicketOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["support"])


@router.post("/tickets", response_model=SupportTicketOut, status_code=201)
async def create_ticket(
    body: SupportTicketCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> SupportTicketOut:
    logger.info("create_ticket user=%s subject_len=%s", user.id, len(body.subject))

    ticket = SupportTicket(
        user_id=user.id,
        subject=body.subject,
        body=body.body,
        status=TicketStatus.OPEN,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    logger.info("create_ticket done ticket_id=%s user=%s", ticket.id, user.id)
    return SupportTicketOut.model_validate(ticket)


@router.get("/tickets", response_model=PaginatedResponse[SupportTicketOut])
async def list_tickets(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[SupportTicketOut]:
    logger.info("list_tickets user=%s page=%s page_size=%s", user.id, page, page_size)

    where = [SupportTicket.user_id == user.id]

    count_result = await db.execute(
        select(func.count()).select_from(SupportTicket).where(*where)
    )
    total: int = count_result.scalar_one()

    total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1

    rows_result = await db.execute(
        select(SupportTicket)
        .where(*where)
        .order_by(SupportTicket.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = rows_result.scalars().all()

    items = [SupportTicketOut.model_validate(row) for row in rows]

    return PaginatedResponse[SupportTicketOut](
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        has_more=page < total_pages,
    )
