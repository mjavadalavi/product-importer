from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.import_job import ImportJob
from app.db.session import AsyncSessionLocal
from app.services.jobs_service import JobsService

logger = get_logger(__name__)

_worker_task: asyncio.Task[None] | None = None


async def enqueue_job(db: AsyncSession, product_id: uuid.UUID) -> ImportJob:
    return await JobsService(db).enqueue(product_id)


async def claim_next_job(db: AsyncSession) -> ImportJob | None:
    return await JobsService(db).claim_next()


async def run_one(job: ImportJob, db: AsyncSession) -> None:
    await JobsService(db).run_one(job)


async def worker_loop() -> None:
    logger.info("job worker loop started")
    while True:
        try:
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    job = await claim_next_job(db)
                    if job is None:
                        await asyncio.sleep(2)
                        continue
                    await run_one(job, db)
        except asyncio.CancelledError:
            logger.info("job worker loop cancelled")
            break
        except Exception as exc:
            logger.exception("worker loop error: %s", exc)
            await asyncio.sleep(2)


def start_worker() -> None:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(worker_loop())
        logger.info("started background worker task")
