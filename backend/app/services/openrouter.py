"""Shim — thin wrappers that delegate to OpenRouterService.

All existing callers (processing.py, etc.) continue to work without changes.
OpenRouterError is re-exported so ``from app.services.openrouter import OpenRouterError``
keeps working.
"""
from __future__ import annotations

from typing import Any

from app.core.exceptions import OpenRouterError  # noqa: F401  re-export
from app.services.openrouter_service import OpenRouterService


async def analyze_product_image(
    *,
    image_data_url: str,
    categories: list[dict[str, Any]],
    openrouter_key: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    service = OpenRouterService(api_key=openrouter_key)
    return await service.analyze_product_image(
        image_data_url=image_data_url,
        categories=categories,
        model=model,
    )


async def enhance_product_image(
    *,
    image_data_url: str,
    filename: str = "product.jpg",
    openrouter_key: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    service = OpenRouterService(api_key=openrouter_key)
    return await service.enhance_product_image(
        image_data_url=image_data_url,
        filename=filename,
        model=model,
    )
