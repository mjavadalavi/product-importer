from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.product import ProductStatus


class ProductImageIn(BaseModel):
    filename: str = "product.jpg"
    data_url: str = Field(..., min_length=20)

    @field_validator("data_url")
    @classmethod
    def must_be_data_url(cls, v: str) -> str:
        if not v.startswith("data:"):
            raise ValueError("data_url must start with 'data:'")
        return v


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
