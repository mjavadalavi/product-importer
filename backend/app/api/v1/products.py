from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.crypto import decrypt_token
from app.auth.deps import require_user
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.db.models.oauth_account import OAuthAccount
from app.db.models.product import Product, ProductStatus
from app.db.models.product_image import ProductImage
from app.db.models.transaction import ReferenceType, Transaction, TransactionStatus
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.products import (
    ProductCreateRequest,
    ProductCreatedResponse,
    ProductImageOut,
    ProductListItem,
    ProductOut,
    ProductUpdateRequest,
)
from app.services import jobs, ledger
from app.services.basalam import BasalamClient
from app.services.basalam.payload import _toman_to_provider_rial

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["products"])


# ---------------------------------------------------------------------------
# POST /  — create a new product and enqueue the import job
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=ProductCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product import job",
)
async def create_product(
    request: ProductCreateRequest,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductCreatedResponse:
    """
    Withdraw cost from the user's wallet first (option a), then create the
    Product + ProductImage rows and enqueue the background import job.

    If the user has insufficient balance, InsufficientBalance (402) bubbles
    up to the global exception handler — no rows are persisted.
    """
    settings = get_settings()
    cost: int = settings.cost_per_product

    logger.info(
        "create_product user_id=%s image_count=%d cost=%d",
        user.id,
        len(request.images),
        cost,
    )

    # Withdraw first so that if it fails nothing has been written yet.
    tx = await ledger.withdraw(db, user.id, ReferenceType.PRODUCT, None, cost)
    logger.debug("withdraw succeeded tx_id=%s", tx.id)

    # Create the product row.
    product = Product(user_id=user.id, status=ProductStatus.DRAFT)
    if request.description:
        product.description = request.description
    db.add(product)
    await db.flush()  # obtain product.id

    # Create image rows in order.
    for idx, img in enumerate(request.images):
        image = ProductImage(
            product_id=product.id,
            order=idx,
            original_url=img.data_url,
            filename=img.filename,
            use_enhanced=False,
        )
        db.add(image)

    await db.flush()

    # Link the transaction to this product and advance status.
    product.withdraw_tx_id = tx.id
    product.status = ProductStatus.PROCESSING

    # Enqueue the background processing job (flushes inside).
    job = await jobs.enqueue_job(db, product.id)
    logger.info(
        "product queued product_id=%s job_id=%s",
        product.id,
        job.id,
    )

    await db.commit()

    return ProductCreatedResponse(product_id=product.id, status=product.status)


# ---------------------------------------------------------------------------
# GET /  — list products owned by the current user
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=PaginatedResponse[ProductListItem],
    summary="List products for the current user",
)
async def list_products(
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    product_status: ProductStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[ProductListItem]:
    """Return a paginated list of the user's products, newest first."""
    base_filter = [Product.user_id == user.id]
    if product_status is not None:
        base_filter.append(Product.status == product_status)

    # Total count query.
    count_result = await db.execute(
        select(func.count(Product.id)).where(*base_filter)
    )
    total: int = count_result.scalar_one()

    # Data query with eager-loaded images.
    offset = (page - 1) * page_size
    rows_result = await db.execute(
        select(Product)
        .where(*base_filter)
        .order_by(Product.created_at.desc())
        .options(selectinload(Product.images))
        .offset(offset)
        .limit(page_size)
    )
    rows = rows_result.scalars().all()

    items = [ProductListItem.from_product(row) for row in rows]

    logger.debug(
        "list_products user_id=%s total=%d page=%d page_size=%d",
        user.id,
        total,
        page,
        page_size,
    )

    return PaginatedResponse.build(items=items, page=page, page_size=page_size, total=total)


# ---------------------------------------------------------------------------
# GET /{product_id}  — retrieve a single product
# ---------------------------------------------------------------------------

@router.get(
    "/{product_id}",
    response_model=ProductOut,
    summary="Get product detail",
)
async def get_product(
    product_id: UUID,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductOut:
    """Return full product detail.  Raises 404 if not found or not owned."""
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id, Product.user_id == user.id)
        .options(selectinload(Product.images))
    )
    product = result.scalar_one_or_none()
    if product is None:
        logger.warning("get_product not found product_id=%s user_id=%s", product_id, user.id)
        raise NotFoundError()

    return ProductOut.model_validate(product)


# ---------------------------------------------------------------------------
# PATCH /{product_id}  — update editable fields, optionally push to Basalam
# ---------------------------------------------------------------------------

@router.patch(
    "/{product_id}",
    response_model=ProductOut,
    summary="Update product fields",
)
async def update_product(
    product_id: UUID,
    request: ProductUpdateRequest,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductOut:
    """
    Apply only the fields that are explicitly set in the request body.

    If the product has already been submitted to Basalam (`basalam_product_id`
    is set), the changed fields are also pushed via the Basalam API.  A failure
    there does NOT roll back the local update; instead the error is stored in
    `product.errors["basalam_update"]` and the response still returns 200.
    """
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id, Product.user_id == user.id)
        .options(selectinload(Product.images))
    )
    product = result.scalar_one_or_none()
    if product is None:
        logger.warning("update_product not found product_id=%s user_id=%s", product_id, user.id)
        raise NotFoundError()

    updated_fields = request.model_dump(exclude_unset=True)
    logger.info(
        "update_product product_id=%s fields=%s", product_id, list(updated_fields.keys())
    )

    for field, value in updated_fields.items():
        setattr(product, field, value)

    # Optionally push to Basalam when the product is already live.
    if product.basalam_product_id and updated_fields:
        basalam_payload: dict = {}

        field_map = {
            "name": "name",
            "brief": "brief",
            "description": "description",
            "stock": "stock",
            "preparation_days": "preparation_days",
            "weight": "weight",
            "package_weight": "package_weight",
        }
        for local_field, remote_field in field_map.items():
            if local_field in updated_fields:
                basalam_payload[remote_field] = updated_fields[local_field]

        # price_final is stored in toman; Basalam expects rial.
        if "price_final" in updated_fields:
            basalam_payload["primary_price"] = _toman_to_provider_rial(
                updated_fields["price_final"]
            )

        if basalam_payload:
            try:
                # Fetch the encrypted OAuth token for this user.
                oauth_result = await db.execute(
                    select(OAuthAccount).where(
                        OAuthAccount.user_id == user.id,
                        OAuthAccount.provider == "basalam",
                    )
                )
                oauth = oauth_result.scalar_one_or_none()
                if oauth is None:
                    raise ValueError("no basalam oauth account found for user")

                decrypted_token = decrypt_token(oauth.access_token_enc)
                client = BasalamClient(token=decrypted_token)
                await client.update_product(product.basalam_product_id, basalam_payload)
                logger.info(
                    "basalam product updated product_id=%s basalam_product_id=%s",
                    product_id,
                    product.basalam_product_id,
                )
            except Exception as exc:
                logger.warning(
                    "basalam update failed product_id=%s error=%s",
                    product_id,
                    exc,
                )
                # Persist the error but do not roll back.
                existing_errors: dict = product.errors or {}
                existing_errors["basalam_update"] = str(exc)
                product.errors = existing_errors

    await db.commit()
    await db.refresh(product)

    return ProductOut.model_validate(product)


# ---------------------------------------------------------------------------
# POST /{product_id}/resubmit  — re-queue a failed or ready product
# ---------------------------------------------------------------------------

@router.post(
    "/{product_id}/resubmit",
    response_model=ProductCreatedResponse,
    summary="Resubmit a failed or ready product for processing",
)
async def resubmit_product(
    product_id: UUID,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductCreatedResponse:
    """
    Re-enqueue an import job for a product that has status FAILED or READY.

    If the previous withdraw transaction was REVERSED (i.e. refunded), a new
    withdraw is taken before re-queuing.
    """
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id, Product.user_id == user.id)
    )
    product = result.scalar_one_or_none()
    if product is None:
        logger.warning(
            "resubmit_product not found product_id=%s user_id=%s", product_id, user.id
        )
        raise NotFoundError()

    allowed_statuses = {ProductStatus.FAILED, ProductStatus.READY}
    if product.status not in allowed_statuses:
        logger.warning(
            "resubmit_product invalid status product_id=%s status=%s",
            product_id,
            product.status,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot resubmit a product with status '{product.status}'.",
        )

    settings = get_settings()
    cost: int = settings.cost_per_product

    # If the previous transaction was reversed (refunded), take a new charge.
    if product.withdraw_tx_id is not None:
        prev_tx = await db.get(Transaction, product.withdraw_tx_id)
        if prev_tx is not None and prev_tx.status == TransactionStatus.REVERSED:
            logger.info(
                "resubmit_product previous tx reversed — taking new withdraw product_id=%s",
                product_id,
            )
            new_tx = await ledger.withdraw(
                db, user.id, ReferenceType.PRODUCT, None, cost
            )
            product.withdraw_tx_id = new_tx.id
            logger.debug("new withdraw tx_id=%s", new_tx.id)
    else:
        # No previous transaction recorded at all — charge the user.
        logger.info(
            "resubmit_product no previous tx — taking fresh withdraw product_id=%s",
            product_id,
        )
        new_tx = await ledger.withdraw(
            db, user.id, ReferenceType.PRODUCT, None, cost
        )
        product.withdraw_tx_id = new_tx.id

    # Advance status and clear any prior error payload.
    product.status = ProductStatus.PROCESSING
    product.errors = None

    job = await jobs.enqueue_job(db, product.id)
    logger.info(
        "resubmit_product queued product_id=%s job_id=%s", product.id, job.id
    )

    await db.commit()

    return ProductCreatedResponse(product_id=product.id, status=product.status)
