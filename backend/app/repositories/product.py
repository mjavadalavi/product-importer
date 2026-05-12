"""
Product, ProductImage, and ImportJob repositories for the product-importer backend.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.import_job import ImportJob, JobStatus
from app.db.models.product import Product, ProductStatus
from app.db.models.product_image import ProductImage
from app.repositories.base import BaseRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)

# All five statuses used as defaults in count_by_status.
_ALL_STATUSES: tuple[ProductStatus, ...] = (
    ProductStatus.DRAFT,
    ProductStatus.PROCESSING,
    ProductStatus.READY,
    ProductStatus.SUBMITTED,
    ProductStatus.FAILED,
)


class ProductRepository(BaseRepository[Product]):
    """Repository for Product model operations in product-importer."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Product, session)

    async def get_for_user(
        self,
        product_id: UUID,
        user_id: UUID,
        *,
        with_images: bool = False,
    ) -> Optional[Product]:
        """
        Fetch a single product owned by *user_id*.

        Returns None when no matching row exists; never raises.
        Eagerly loads images when *with_images* is True to avoid a lazy-load
        outside the session.
        """
        query = select(Product).where(
            Product.id == product_id,
            Product.user_id == user_id,
        )
        if with_images:
            query = query.options(selectinload(Product.images))

        result = await self.session.execute(query)
        product = result.scalar_one_or_none()
        logger.debug(
            "get_for_user: product_id=%s user_id=%s found=%s with_images=%s",
            product_id,
            user_id,
            product is not None,
            with_images,
        )
        return product

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        status: Optional[ProductStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Product], int]:
        """
        Paginated list of products for *user_id*, optionally filtered by *status*.

        Returns a 2-tuple (rows, total_count).  Images are loaded via
        selectinload to avoid N+1 round-trips.  The total count comes from a
        separate COUNT(*) query so it reflects the un-paginated result set.
        """
        base_filters = [Product.user_id == user_id]
        if status is not None:
            base_filters.append(Product.status == status)

        # Total count (no pagination, no eager loads needed).
        count_query = (
            select(func.count())
            .select_from(Product)
            .where(*base_filters)
        )
        count_result = await self.session.execute(count_query)
        total: int = count_result.scalar() or 0

        # Paginated rows with images.
        offset = (page - 1) * page_size
        rows_query = (
            select(Product)
            .where(*base_filters)
            .options(selectinload(Product.images))
            .order_by(Product.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows_result = await self.session.execute(rows_query)
        rows = list(rows_result.scalars().all())

        logger.debug(
            "list_for_user: user_id=%s status=%s page=%d page_size=%d total=%d returned=%d",
            user_id,
            status,
            page,
            page_size,
            total,
            len(rows),
        )
        return rows, total

    async def count_by_status(self, user_id: UUID) -> dict[ProductStatus, int]:
        """
        Return a count per ProductStatus for *user_id*.

        All five statuses are always present in the result dict (defaulting to
        0) so callers never need to guard against missing keys.
        """
        query = (
            select(Product.status, func.count().label("cnt"))
            .where(Product.user_id == user_id)
            .group_by(Product.status)
        )
        result = await self.session.execute(query)
        rows = result.all()

        # Seed every status with 0 so the full set is always returned.
        counts: dict[ProductStatus, int] = {s: 0 for s in _ALL_STATUSES}
        for row in rows:
            counts[row.status] = row.cnt

        logger.debug(
            "count_by_status: user_id=%s counts=%s", user_id, counts
        )
        return counts

    async def get_drafts_for_user(
        self,
        user_id: UUID,
        *,
        ids: Optional[list[UUID]] = None,
    ) -> list[Product]:
        """
        Return DRAFT products for *user_id*.

        When *ids* is supplied only products whose id is in the list are
        returned; otherwise all drafts for the user are returned.
        """
        filters = [
            Product.user_id == user_id,
            Product.status == ProductStatus.DRAFT,
        ]
        if ids is not None:
            filters.append(Product.id.in_(ids))

        query = (
            select(Product)
            .where(*filters)
            .order_by(Product.created_at.desc())
        )
        result = await self.session.execute(query)
        drafts = list(result.scalars().all())
        logger.debug(
            "get_drafts_for_user: user_id=%s ids=%s returned=%d",
            user_id,
            ids,
            len(drafts),
        )
        return drafts


class ProductImageRepository(BaseRepository[ProductImage]):
    """Repository for ProductImage model operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ProductImage, session)

    async def list_for_product(self, product_id: UUID) -> list[ProductImage]:
        """Return all images for *product_id* ordered by their display order."""
        query = (
            select(ProductImage)
            .where(ProductImage.product_id == product_id)
            .order_by(ProductImage.order)
        )
        result = await self.session.execute(query)
        images = list(result.scalars().all())
        logger.debug(
            "list_for_product: product_id=%s returned=%d", product_id, len(images)
        )
        return images

    async def next_order(self, product_id: UUID) -> int:
        """
        Return the next available display-order index for *product_id*.

        Returns 0 when no images exist yet; otherwise max(order)+1.
        """
        query = select(func.max(ProductImage.order)).where(
            ProductImage.product_id == product_id
        )
        result = await self.session.execute(query)
        max_order: Optional[int] = result.scalar()
        next_idx = 0 if max_order is None else max_order + 1
        logger.debug(
            "next_order: product_id=%s next=%d", product_id, next_idx
        )
        return next_idx

    async def get_for_product(
        self, image_id: UUID, product_id: UUID
    ) -> Optional[ProductImage]:
        """
        Fetch a single image belonging to *product_id*.

        Returns None when not found; never raises.
        """
        query = select(ProductImage).where(
            ProductImage.id == image_id,
            ProductImage.product_id == product_id,
        )
        result = await self.session.execute(query)
        image = result.scalar_one_or_none()
        logger.debug(
            "get_for_product: image_id=%s product_id=%s found=%s",
            image_id,
            product_id,
            image is not None,
        )
        return image


class ImportJobRepository(BaseRepository[ImportJob]):
    """Repository for ImportJob model operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ImportJob, session)

    async def enqueue(self, product_id: UUID) -> ImportJob:
        """
        Create a new QUEUED ImportJob for *product_id* and flush it.

        The caller is responsible for committing the transaction.
        """
        job = ImportJob(product_id=product_id, status=JobStatus.QUEUED)
        self.session.add(job)
        await self.session.flush()
        logger.info(
            "enqueue: job_id=%s product_id=%s", job.id, product_id
        )
        return job

    async def claim_next_queued(self) -> Optional[ImportJob]:
        """
        Atomically claim the next QUEUED job.

        Issues a SELECT … FOR UPDATE SKIP LOCKED so that concurrent workers
        never pick up the same row.  Transitions the job to RUNNING, records
        started_at, and increments attempts.  Flushes (does NOT commit) so
        the lock is held until the caller commits.

        Returns None when no QUEUED job is available.
        """
        result = await self.session.execute(
            select(ImportJob)
            .where(ImportJob.status == JobStatus.QUEUED)
            .order_by(ImportJob.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = result.scalar_one_or_none()
        if job is None:
            logger.debug("claim_next_queued: no QUEUED job available")
            return None

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(tz=timezone.utc)
        job.attempts += 1
        await self.session.flush()

        logger.info(
            "claim_next_queued: claimed job_id=%s product_id=%s attempts=%d",
            job.id,
            job.product_id,
            job.attempts,
        )
        return job
