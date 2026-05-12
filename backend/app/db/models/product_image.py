from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UUIDType


class ProductImage(Base):
    __tablename__ = "product_images"
    __table_args__ = (
        Index("ix_product_images_file_id", "file_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Optional reference to the generic files table (Wave B).
    # NULL when the image was supplied as a raw data_url by an older client.
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    original_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    enhanced_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    use_enhanced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, default="product.jpg")
    enhancement_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    enhancement_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="images")  # noqa: F821
    # Lazy="joined" so the File row is loaded in the same SELECT as ProductImage.
    # "File | None" because file_id is nullable.
    file: Mapped["File | None"] = relationship("File", lazy="joined")  # noqa: F821
