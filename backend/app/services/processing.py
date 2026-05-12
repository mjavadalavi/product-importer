"""Shim — re-exports process_product_job from processing_service.

Existing callers (jobs.py worker_loop) continue to work without changes.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.processing_service import ProcessingService


async def process_product_job(product_id: UUID, db: AsyncSession) -> None:
    service = ProcessingService(db)
    return await service.process_product_job(product_id)
