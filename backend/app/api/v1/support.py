from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_user
from app.db.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.support import SupportTicketCreate, SupportTicketOut
from app.services.support_service import SupportService

router = APIRouter(prefix="/support", tags=["support"])


@router.post("/tickets", response_model=SupportTicketOut, status_code=201)
async def create_ticket(
    body: SupportTicketCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> SupportTicketOut:
    ticket = await SupportService(db).create(user.id, body)
    return SupportTicketOut.model_validate(ticket)


@router.get("/tickets", response_model=PaginatedResponse[SupportTicketOut])
async def list_tickets(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[SupportTicketOut]:
    return await SupportService(db).list_for_user(user.id, page=page, page_size=page_size)
