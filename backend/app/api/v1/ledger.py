from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db.models.transaction import GeneralType, Transaction, TransactionStatus
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.ledger import TopupRequest, TransactionOut
from app.services import ledger

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
        user.id,
        type,
        status,
        page,
        page_size,
    )

    base_where = [Transaction.user_id == user.id]
    if type is not None:
        base_where.append(Transaction.general_type == type)
    if status is not None:
        base_where.append(Transaction.status == status)

    count_result = await db.execute(
        select(func.count()).select_from(Transaction).where(*base_where)
    )
    total: int = count_result.scalar_one()

    total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1

    rows_result = await db.execute(
        select(Transaction)
        .where(*base_where)
        .order_by(Transaction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = rows_result.scalars().all()

    items = [TransactionOut.model_validate(row) for row in rows]

    return PaginatedResponse[TransactionOut](
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        has_more=page < total_pages,
    )


@router.post("/topup", response_model=TransactionOut)
async def request_topup(
    body: TopupRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> TransactionOut:
    logger.info("request_topup user=%s amount=%s", user.id, body.amount)

    tx = await ledger.request_topup(db, user.id, body.amount)
    await db.commit()
    await db.refresh(tx)

    logger.info("topup created tx_id=%s user=%s amount=%s", tx.id, user.id, body.amount)
    return TransactionOut.model_validate(tx)
