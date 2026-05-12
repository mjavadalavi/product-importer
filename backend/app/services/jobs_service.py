from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.import_job import ImportJob, JobStatus
from app.repositories.product import ImportJobRepository
from app.utils.logging import LoggerMixin


class JobsService(LoggerMixin):
    """Business logic layer for import-job lifecycle management."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ImportJobRepository(session)

    async def enqueue(self, product_id: UUID) -> ImportJob:
        """Create and flush a new QUEUED job for *product_id*."""
        job = await self.repo.enqueue(product_id)
        self.logger.info("enqueue: job_id=%s product_id=%s", job.id, product_id)
        return job

    async def claim_next(self) -> ImportJob | None:
        """Atomically claim the next QUEUED job; returns None when the queue is empty."""
        return await self.repo.claim_next_queued()

    async def run_one(self, job: ImportJob) -> None:
        """
        Process *job* to completion.

        - On success:  status = SUCCEEDED
        - On failure:  status = FAILED, error = str(exc)
        - Always:      finished_at = utcnow()

        The late import of processing breaks the circular dependency between
        jobs_service and processing modules.
        """
        # Late import to avoid circular dependency at module load time.
        from app.services.processing import process_product_job

        try:
            await process_product_job(job.product_id, db=self.session)
            job.status = JobStatus.SUCCEEDED
            job.finished_at = datetime.now(tz=timezone.utc)
            self.logger.info("run_one: job succeeded job_id=%s", job.id)
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.finished_at = datetime.now(tz=timezone.utc)
            self.logger.exception(
                "run_one: job failed job_id=%s error=%s", job.id, exc
            )
