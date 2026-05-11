from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UUIDType


class GeneralType(str, enum.Enum):
    WITHDRAW = "WITHDRAW"
    DEPOSIT = "DEPOSIT"


class ReferenceType(str, enum.Enum):
    PRODUCT = "PRODUCT"
    SUBSCRIPTION = "SUBSCRIPTION"
    PAYMENT = "PAYMENT"
    REFERRAL = "REFERRAL"
    GIFT = "GIFT"
    REQUEST_AMOUNT = "REQUEST_AMOUNT"


class TransactionStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_user_status", "user_id", "status"),
        Index(
            "uq_transactions_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where="idempotency_key IS NOT NULL",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    general_type: Mapped[GeneralType] = mapped_column(
        Enum(GeneralType, name="general_type_enum"), nullable=False
    )
    reference_type: Mapped[ReferenceType] = mapped_column(
        Enum(ReferenceType, name="reference_type_enum"), nullable=False
    )
    reference_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    amount: Mapped[int] = mapped_column(Numeric(14, 0), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, name="transaction_status_enum"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="transactions")  # noqa: F821
