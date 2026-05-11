"""
Integration tests for the products API: POST /api/v1/products, GET, PATCH.
"""
from __future__ import annotations

import uuid as _uuid_module

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.import_job import ImportJob, JobStatus
from app.db.models.product import Product, ProductStatus
from app.db.models.product_image import ProductImage
from app.db.models.transaction import (
    GeneralType,
    ReferenceType,
    Transaction,
    TransactionStatus,
)
from app.services import ledger

# A minimal valid data-URL (1x1 transparent PNG encoded as base64).
_TINY_DATA_URL = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _give_balance(db: AsyncSession, user_id, amount: int) -> Transaction:
    """Insert a completed GIFT deposit directly."""
    return await ledger.deposit(
        db,
        user_id=user_id,
        ref_type=ReferenceType.GIFT,
        ref_id=None,
        amount=amount,
        status=TransactionStatus.COMPLETED,
    )


def _product_payload(image_count: int = 1) -> dict:
    return {
        "images": [
            {"filename": "photo.jpg", "data_url": _TINY_DATA_URL}
            for _ in range(image_count)
        ]
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_create_product_insufficient_balance(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user,
    auth_cookie,
):
    """POST /products with 0 balance should return 402."""
    user = await make_user()
    # No deposit — balance is 0.
    cookies = auth_cookie(user)

    response = await client.post(
        "/api/v1/products/",
        json=_product_payload(1),
        cookies=cookies,
    )
    assert response.status_code == 402


async def test_create_product_charges_and_enqueues(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user,
    auth_cookie,
):
    """
    POST /products with sufficient balance should:
    - Return 201 with status PROCESSING.
    - Create a Product row.
    - Create a ProductImage row.
    - Create a PENDING WITHDRAW PRODUCT transaction.
    - Create an ImportJob with status QUEUED.
    """
    settings = get_settings()
    user = await make_user()
    await _give_balance(db_session, user.id, 5)
    await db_session.flush()

    cookies = auth_cookie(user)
    response = await client.post(
        "/api/v1/products/",
        json=_product_payload(1),
        cookies=cookies,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PROCESSING"

    product_id_str = body["product_id"]
    product_id = _uuid_module.UUID(product_id_str)

    # Product row exists.
    product_result = await db_session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = product_result.scalar_one_or_none()
    assert product is not None
    assert product.status == ProductStatus.PROCESSING

    # Image row exists.
    img_result = await db_session.execute(
        select(ProductImage).where(ProductImage.product_id == product_id)
    )
    images = img_result.scalars().all()
    assert len(images) == 1

    # PENDING WITHDRAW PRODUCT transaction exists.
    tx_result = await db_session.execute(
        select(Transaction).where(
            Transaction.user_id == user.id,
            Transaction.general_type == GeneralType.WITHDRAW,
            Transaction.reference_type == ReferenceType.PRODUCT,
            Transaction.status == TransactionStatus.PENDING,
            Transaction.amount == settings.cost_per_product,
        )
    )
    tx = tx_result.scalar_one_or_none()
    assert tx is not None

    # ImportJob exists with QUEUED status.
    job_result = await db_session.execute(
        select(ImportJob).where(ImportJob.product_id == product_id)
    )
    job = job_result.scalar_one_or_none()
    assert job is not None
    assert job.status == JobStatus.QUEUED


async def test_get_products_returns_user_products_only(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user,
    auth_cookie,
):
    """
    GET /products as user1 should return only user1's products (not user2's).
    """
    settings = get_settings()

    user1 = await make_user(basalam_user_id=11001)
    user2 = await make_user(basalam_user_id=11002)

    # Give both users enough balance.
    await _give_balance(db_session, user1.id, 5)
    await _give_balance(db_session, user2.id, 5)
    await db_session.flush()

    # Create a product for user1.
    response1 = await client.post(
        "/api/v1/products/",
        json=_product_payload(1),
        cookies=auth_cookie(user1),
    )
    assert response1.status_code == 201

    # Create a product for user2.
    response2 = await client.post(
        "/api/v1/products/",
        json=_product_payload(1),
        cookies=auth_cookie(user2),
    )
    assert response2.status_code == 201

    # Fetch user1's product list.
    list_response = await client.get(
        "/api/v1/products/",
        cookies=auth_cookie(user1),
    )
    assert list_response.status_code == 200
    data = list_response.json()

    # Only user1's product should be in the response.
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert str(data["items"][0]["id"]) == response1.json()["product_id"]


async def test_get_product_detail_404_for_other_user(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user,
    auth_cookie,
):
    """
    GET /products/{id} should return 404 when the product belongs to another user.
    """
    user1 = await make_user(basalam_user_id=22001)
    user2 = await make_user(basalam_user_id=22002)

    await _give_balance(db_session, user1.id, 5)
    await db_session.flush()

    # Create a product as user1.
    create_resp = await client.post(
        "/api/v1/products/",
        json=_product_payload(1),
        cookies=auth_cookie(user1),
    )
    assert create_resp.status_code == 201
    product_id = create_resp.json()["product_id"]

    # Try to fetch that product as user2 — should be 404.
    detail_resp = await client.get(
        f"/api/v1/products/{product_id}",
        cookies=auth_cookie(user2),
    )
    assert detail_resp.status_code == 404


async def test_patch_product_updates_fields(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user,
    auth_cookie,
):
    """
    PATCH /products/{id} should update the given fields and return the updated product.
    """
    user = await make_user(basalam_user_id=33001)

    await _give_balance(db_session, user.id, 5)
    await db_session.flush()

    # Create the product.
    create_resp = await client.post(
        "/api/v1/products/",
        json=_product_payload(1),
        cookies=auth_cookie(user),
    )
    assert create_resp.status_code == 201
    product_id_str = create_resp.json()["product_id"]
    product_id = _uuid_module.UUID(product_id_str)

    # PATCH with a new name.
    patch_resp = await client.patch(
        f"/api/v1/products/{product_id_str}",
        json={"name": "Updated Product Name"},
        cookies=auth_cookie(user),
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["name"] == "Updated Product Name"

    # Verify in DB.
    product_result = await db_session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = product_result.scalar_one_or_none()
    assert product is not None
    assert product.name == "Updated Product Name"
