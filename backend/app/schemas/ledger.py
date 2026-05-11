from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.transaction import GeneralType, ReferenceType, TransactionStatus


class TopupRequest(BaseModel):
    amount: int = Field(..., ge=1000, le=100_000_000)


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    general_type: GeneralType
    reference_type: ReferenceType
    reference_id: int | None
    amount: int
    status: TransactionStatus
    note: str | None
    created_at: datetime


class TransactionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    general_type: GeneralType
    reference_type: ReferenceType
    reference_id: int | None
    amount: int
    status: TransactionStatus
    note: str | None
    created_at: datetime
