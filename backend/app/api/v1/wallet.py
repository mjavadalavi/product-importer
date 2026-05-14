"""Wallet endpoints — top-up via the Shopyaar payment bridge."""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db.models.user import User
from app.db.session import get_db
from app.services.wallet_service import WalletError, WalletService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wallet", tags=["wallet"])


class TopupRequest(BaseModel):
    amount: int = Field(..., gt=0, description="مبلغ به تومان")


class TopupResponse(BaseModel):
    transaction_id: str
    token: str
    url: str
    bypass: bool


class VerifyRequest(BaseModel):
    authority: str = Field(..., min_length=1)

    @field_validator("authority")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class VerifyResponse(BaseModel):
    transaction_id: str | None
    success: bool
    status: str
    amount: int
    ref_id: str | None = None


@router.post("/topup", response_model=TopupResponse)
async def start_topup(
    body: TopupRequest,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TopupResponse:
    service = WalletService(db)
    try:
        result = await service.start_topup(user, body.amount)
    except WalletError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return TopupResponse(
        transaction_id=str(result.transaction_id),
        token=result.token,
        url=result.url,
        bypass=result.bypass,
    )


@router.post("/verify", response_model=VerifyResponse)
async def verify_topup(
    body: VerifyRequest,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VerifyResponse:
    service = WalletService(db)
    try:
        result = await service.verify_topup(body.authority)
    except WalletError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return VerifyResponse(
        transaction_id=str(result.transaction_id) if result.transaction_id else None,
        success=result.success,
        status=result.status.value,
        amount=result.amount,
        ref_id=result.ref_id,
    )
