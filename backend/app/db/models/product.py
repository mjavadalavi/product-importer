from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import JSONType, UUIDType


class ProductStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PROCESSING = "PROCESSING"
    READY = "READY"
    SUBMITTED = "SUBMITTED"
    FAILED = "FAILED"


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_user_status", "user_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="product_status_enum"),
        nullable=False,
        default=ProductStatus.DRAFT,
    )
    name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_final: Mapped[int | None] = mapped_column(Numeric(14, 0), nullable=True)
    price_suggested: Mapped[int | None] = mapped_column(Numeric(14, 0), nullable=True)
    price_meta: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    package_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    preparation_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sku: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    variants: Mapped[list[dict] | None] = mapped_column(JSONType, nullable=True)
    ai_result: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    price_samples: Mapped[list[dict] | None] = mapped_column(JSONType, nullable=True)
    basalam_product_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    errors: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    withdraw_tx_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="products")  # noqa: F821
    images: Mapped[list["ProductImage"]] = relationship(  # noqa: F821
        "ProductImage", back_populates="product", cascade="all, delete-orphan", order_by="ProductImage.order"
    )
    import_jobs: Mapped[list["ImportJob"]] = relationship(  # noqa: F821
        "ImportJob", back_populates="product", cascade="all, delete-orphan"
    )
