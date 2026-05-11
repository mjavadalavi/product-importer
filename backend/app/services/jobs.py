from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.import_job import ImportJob, JobStatus
from app.db.session import AsyncSessionLocal

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

_worker_task: asyncio.Task[None] | None = None


async def enqueue_job(db: AsyncSession, product_id: uuid.UUID) -> ImportJob:
    job = ImportJob(product_id=product_id, status=JobStatus.QUEUED)
    db.add(job)
    await db.flush()
    logger.info("enqueued job job_id=%s product_id=%s", job.id, product_id)
    return job


async def claim_next_job(db: AsyncSession) -> ImportJob | None:
    result = await db.execute(
        select(ImportJob)
        .where(ImportJob.status == JobStatus.QUEUED)
        .order_by(ImportJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None
    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(tz=timezone.utc)
    job.attempts += 1
    await db.flush()
    return job


async def run_one(job: ImportJob, db: AsyncSession) -> None:
    from app.services.processing import process_product_job

    try:
        await process_product_job(job.product_id, db=db)
        job.status = JobStatus.SUCCEEDED
        job.finished_at = datetime.now(tz=timezone.utc)
        logger.info("job succeeded job_id=%s", job.id)
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)
        job.finished_at = datetime.now(tz=timezone.utc)
        logger.exception("job failed job_id=%s error=%s", job.id, exc)


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
