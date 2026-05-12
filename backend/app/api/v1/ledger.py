from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db.models.transaction import GeneralType, TransactionStatus
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.ledger import TopupRequest, TransactionOut
from app.services.ledger_service import LedgerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ledger", tags=["ledger"])


@router.get("/transactions", response_model=PaginatedResponse[TransactionOut])
async def list_transactions(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
    type: Optional[GeneralType] = Query(default=None),
    status: Optional[TransactionStatus] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[TransactionOut]:
    logger.info(
        "list_transactions user=%s type=%s status=%s page=%s page_size=%s",
        user.id, type, status, page, page_size,
    )
    service = LedgerService(db)
    rows, total = await service.list_transactions(
        user.id, general_type=type, status=status, page=page, page_size=page_size,
    )
    items = [TransactionOut.model_validate(row) for row in rows]
    return PaginatedResponse[TransactionOut].build(items, page, page_size, total)


@router.post("/topup", response_model=TransactionOut)
async def request_topup(
    body: TopupRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> TransactionOut:
    logger.info("request_topup user=%s amount=%s", user.id, body.amount)
    service = LedgerService(db)
    tx = await service.request_topup(user.id, body.amount)
    await db.commit()
    await db.refresh(tx)
    logger.info("topup created tx_id=%s user=%s amount=%s", tx.id, user.id, body.amount)
    return TransactionOut.model_validate(tx)
