from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UUIDType


class AiCallKind(str, enum.Enum):
    ANALYZE = "ANALYZE"
    ENHANCE = "ENHANCE"
    OTHER = "OTHER"


class AiCallStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class AiCall(Base):
    __tablename__ = "ai_calls"
    __table_args__ = (
        Index("ix_ai_calls_user_created", "user_id", "created_at"),
        Index("ix_ai_calls_product_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[AiCallKind] = mapped_column(
        Enum(AiCallKind, name="ai_call_kind_enum"),
        nullable=False,
    )
    status: Mapped[AiCallStatus] = mapped_column(
        Enum(AiCallStatus, name="ai_call_status_enum"),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float] = mapped_column(
        Numeric(14, 8), nullable=False, default=0
    )
    generation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
