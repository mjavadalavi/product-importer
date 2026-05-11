from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CategoryFlat(BaseModel):
    id: int
    title: str
    path: str
    unit_type: int | None
    is_leaf: bool


class CategoriesResponse(BaseModel):
    flat: list[CategoryFlat]
    raw: Any
