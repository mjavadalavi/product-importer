from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models.product import ProductStatus


class ProductImageIn(BaseModel):
    """Image payload accepted by product endpoints.

    Exactly one of ``file_id`` or ``data_url`` must be provided.
    When both are present ``file_id`` takes precedence (Wave B).
    ``data_url`` is retained as a deprecated alternative for older clients.
    """

    filename: str = "product.jpg"
    # Wave B: reference an already-uploaded File row.
    file_id: uuid.UUID | None = None
    # Deprecated: inline base64 data URL.  Kept for backward compatibility.
    data_url: str | None = Field(default=None, min_length=20)

    @field_validator("data_url")
    @classmethod
    def must_be_data_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("data:"):
            raise ValueError("data_url باید با 'data:' شروع شود")
        return v

    @model_validator(mode="after")
    def require_one_image_source(self) -> "ProductImageIn":
        if self.file_id is None and self.data_url is None:
            raise ValueError("یکی از file_id یا data_url الزامی است")
        return self


class ProductCreateRequest(BaseModel):
    description: str | None = None
    images: list[ProductImageIn] = Field(..., min_length=1, max_length=10)


class PriceSampleOut(BaseModel):
    samples: list[dict[str, Any]] = Field(default_factory=list)


class ProductImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order: int
    original_url: str | None
    enhanced_url: str | None
    use_enhanced: bool
    filename: str
    enhancement_model: str | None
    enhancement_error: str | None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ProductStatus
    name: str | None
    brief: str | None
    description: str | None
    category_id: int | None
    category_title: str | None
    category_confidence: float | None
    price_final: int | None
    price_suggested: int | None
    price_meta: dict[str, Any] | None
    stock: int | None
    weight: float | None
    package_weight: float | None
    preparation_days: int | None
    unit_quantity: float | None
    unit_type: int | None
    sku: str | None
    attributes: dict[str, Any] | None
    variants: list[dict[str, Any]] | None
    ai_result: dict[str, Any] | None
    price_samples: list[dict[str, Any]] | None
    basalam_product_id: int | None
    errors: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    images: list[ProductImageOut]


class ProductListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ProductStatus
    name: str | None
    category_title: str | None
    price_final: int | None
    stock: int | None = None
    preparation_days: int | None = None
    primary_image_url: str | None = None
    created_at: datetime
    basalam_product_id: int | None

    @classmethod
    def from_product(cls, product: Any) -> "ProductListItem":
        first_image = product.images[0] if product.images else None
        primary_url: str | None = None
        if first_image:
            primary_url = (
                first_image.enhanced_url
                if first_image.use_enhanced and first_image.enhanced_url
                else first_image.original_url
            )
        return cls(
            id=product.id,
            status=product.status,
            name=product.name,
            category_title=product.category_title,
            price_final=product.price_final,
            stock=product.stock,
            preparation_days=product.preparation_days,
            primary_image_url=primary_url,
            created_at=product.created_at,
            basalam_product_id=product.basalam_product_id,
        )


class ProductUpdateRequest(BaseModel):
    name: str | None = None
    brief: str | None = None
    description: str | None = None
    category_id: int | None = None
    price_final: int | None = None
    stock: int | None = None
    weight: float | None = None
    package_weight: float | None = None
    preparation_days: int | None = None
    unit_quantity: float | None = None
    unit_type: int | None = None
    sku: str | None = None
    attributes: dict[str, Any] | None = None
    variants: list[dict[str, Any]] | None = None


class ProductCreatedResponse(BaseModel):
    product_id: uuid.UUID
    status: ProductStatus


class BulkDraftImage(BaseModel):
    """Image payload for bulk draft endpoints.

    Exactly one of ``file_id`` or ``data_url`` must be provided.
    When both are present ``file_id`` takes precedence (Wave B).
    ``data_url`` is retained as a deprecated alternative for older clients.
    """

    filename: str = "product.jpg"
    # Wave B: reference an already-uploaded File row.
    file_id: uuid.UUID | None = None
    # Deprecated: inline base64 data URL.  Kept for backward compatibility.
    data_url: str | None = Field(default=None, min_length=20)

    @field_validator("data_url")
    @classmethod
    def must_be_data_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("data:"):
            raise ValueError("data_url باید با 'data:' شروع شود")
        return v

    @model_validator(mode="after")
    def require_one_image_source(self) -> "BulkDraftImage":
        if self.file_id is None and self.data_url is None:
            raise ValueError("یکی از file_id یا data_url الزامی است")
        return self


class BulkDraftRow(BaseModel):
    name: str | None = None
    category_title: str | None = None
    brief: str | None = None
    description: str | None = None
    keywords: list[str] | None = None
    sku: str | None = None
    barcode: str | None = None
    primary_price: int | None = None
    stock: int | None = None
    weight_g: int | None = None
    package_weight_g: int | None = None
    preparation_days: int | None = None
    unit_quantity: float | None = None
    unit_type_title: str | None = None
    is_wholesale: bool | None = None
    images: list[BulkDraftImage] = Field(default_factory=list)


class BulkSaveDraftsRequest(BaseModel):
    rows: list[BulkDraftRow] = Field(..., min_length=1, max_length=200)


class BulkDraftCreated(BaseModel):
    product_id: uuid.UUID
    row_index: int


class BulkSaveDraftsResponse(BaseModel):
    created: list[BulkDraftCreated]


class BulkSaveDraftsFromFilesRequest(BaseModel):
    """Request shape for server-side sheet parsing + optional ZIP image matching."""

    sheet_file_id: UUID
    zip_file_id: UUID | None = None
    # Optional manual column mapping: {sheet_header: canonical_key}
    # When omitted the service auto-detects via COLUMNS title/aliases.
    column_mapping: dict[str, str] | None = None


class AttachImagesRequest(BaseModel):
    images: list[BulkDraftImage] = Field(..., min_length=1, max_length=10)


class BulkImageAssignment(BaseModel):
    product_id: uuid.UUID
    images: list[BulkDraftImage] = Field(..., min_length=1, max_length=10)


class BulkAttachImagesRequest(BaseModel):
    assignments: list[BulkImageAssignment] = Field(..., min_length=1, max_length=200)


class ConfirmAllRequest(BaseModel):
    product_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=200)


class ConfirmAllResultItem(BaseModel):
    product_id: uuid.UUID
    ok: bool
    error: str | None = None


class ConfirmAllResponse(BaseModel):
    confirmed: list[ConfirmAllResultItem]
    failed_count: int
    total_charged: int


class ReorderImagesRequest(BaseModel):
    ordered_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=10)
