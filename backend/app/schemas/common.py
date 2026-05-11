from __future__ import annotations

import math
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, computed_field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_more: bool

    @classmethod
    def build(cls, items: list[T], page: int, page_size: int, total: int) -> "PaginatedResponse[T]":
        total_pages = math.ceil(total / page_size) if page_size > 0 else 0
        return cls(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_more=page < total_pages,
        )


class ErrorResponse(BaseModel):
    message: str
    detail: Any | None = None
