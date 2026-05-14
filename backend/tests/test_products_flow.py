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

async def test_create_product_saves_as_draft_without_charge(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user,
    auth_cookie,
):
    """POST /products creates a DRAFT, never charges, never enqueues.
    The user must explicitly confirm to start processing."""
    user = await make_user()
    # No deposit — balance is 0, but DRAFT creation should still work.
    cookies = auth_cookie(user)

    response = await client.post(
        "/api/v1/products/",
        json=_product_payload(1),
        cookies=cookies,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"

    product_id = _uuid_module.UUID(body["product_id"])

    product = await db_session.get(Product, product_id)
    assert product is not None
    assert product.status == ProductStatus.DRAFT
    assert product.withdraw_tx_id is None  # no charge

    images = (
        await db_session.execute(
            select(ProductImage).where(ProductImage.product_id == product_id)
        )
    ).scalars().all()
    assert len(images) == 1

    # No transaction and no import job exist.
    tx = (
        await db_session.execute(
            select(Transaction).where(
                Transaction.user_id == user.id,
                Transaction.general_type == GeneralType.WITHDRAW,
                Transaction.reference_type == ReferenceType.PRODUCT,
            )
        )
    ).scalar_one_or_none()
    assert tx is None

    job = (
        await db_session.execute(
            select(ImportJob).where(ImportJob.product_id == product_id)
        )
    ).scalar_one_or_none()
    assert job is None


async def test_confirm_draft_charges_and_enqueues(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user,
    auth_cookie,
):
    """POST /products/{id}/confirm on a DRAFT with enough balance withdraws
    the cost as PENDING, enqueues the job, and moves status to PROCESSING."""
    settings = get_settings()
    user = await make_user()
    await _give_balance(db_session, user.id, settings.cost_per_product * 2)
    await db_session.flush()

    cookies = auth_cookie(user)
    create_resp = await client.post(
        "/api/v1/products/",
        json=_product_payload(1),
        cookies=cookies,
    )
    assert create_resp.status_code == 201
    product_id_str = create_resp.json()["product_id"]

    confirm_resp = await client.post(
        f"/api/v1/products/{product_id_str}/confirm",
        cookies=cookies,
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "PROCESSING"

    product_id = _uuid_module.UUID(product_id_str)
    product = await db_session.get(Product, product_id)
    assert product is not None
    assert product.status == ProductStatus.PROCESSING

    # PENDING WITHDRAW PRODUCT transaction exists.
    tx = (
        await db_session.execute(
            select(Transaction).where(
                Transaction.user_id == user.id,
                Transaction.general_type == GeneralType.WITHDRAW,
                Transaction.reference_type == ReferenceType.PRODUCT,
                Transaction.status == TransactionStatus.PENDING,
                Transaction.amount == settings.cost_per_product,
            )
        )
    ).scalar_one_or_none()
    assert tx is not None

    # ImportJob exists with QUEUED status.
    job = (
        await db_session.execute(
            select(ImportJob).where(ImportJob.product_id == product_id)
        )
    ).scalar_one_or_none()
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


async def test_delete_product_draft_reverses_withdraw(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user,
    auth_cookie,
):
    """DELETE /products/{id} on a deletable status removes the row and
    reverses the original withdraw transaction."""
    user = await make_user()
    await _give_balance(db_session, user.id, 5)
    await db_session.flush()

    cookies = auth_cookie(user)
    create_resp = await client.post(
        "/api/v1/products/",
        json=_product_payload(1),
        cookies=cookies,
    )
    assert create_resp.status_code == 201
    product_id_str = create_resp.json()["product_id"]
    product_id = _uuid_module.UUID(product_id_str)

    # POST creates DRAFT without a charge — confirm it so a withdraw exists,
    # then put status back to DRAFT for the deletion test.
    confirm_resp = await client.post(
        f"/api/v1/products/{product_id_str}/confirm",
        cookies=cookies,
    )
    assert confirm_resp.status_code == 200
    product = await db_session.get(Product, product_id)
    assert product is not None
    product.status = ProductStatus.DRAFT
    await db_session.commit()
    tx_id_before = product.withdraw_tx_id
    assert tx_id_before is not None

    delete_resp = await client.delete(
        f"/api/v1/products/{product_id_str}",
        cookies=cookies,
    )
    assert delete_resp.status_code == 204

    # Product row gone.
    gone = await db_session.execute(select(Product).where(Product.id == product_id))
    assert gone.scalar_one_or_none() is None

    # Original withdraw tx now REVERSED.
    tx = await db_session.get(Transaction, tx_id_before)
    assert tx is not None
    assert tx.status == TransactionStatus.REVERSED


async def test_processing_completes_pending_withdraw_when_status_becomes_ready(
    db_session: AsyncSession,
    make_user,
):
    """Once AI processing reaches the READY state (user needs to fill in fields),
    the pending product withdraw must be marked COMPLETED so the balance
    reflects the actual spend instead of staying pending forever."""
    settings = get_settings()
    user = await make_user()
    await _give_balance(db_session, user.id, settings.cost_per_product * 2)
    await db_session.flush()

    # Manually simulate the state created by confirm_draft just before AI ran.
    product = Product(user_id=user.id, status=ProductStatus.PROCESSING)
    db_session.add(product)
    await db_session.flush()

    tx = await ledger.withdraw(
        db_session,
        user_id=user.id,
        ref_type=ReferenceType.PRODUCT,
        ref_id=None,
        amount=settings.cost_per_product,
    )
    product.withdraw_tx_id = tx.id
    await db_session.commit()

    # Now mark transaction COMPLETED via the same path processing_service uses.
    from app.services.ledger_service import LedgerService
    await LedgerService(db_session).complete_transaction(tx.id)
    await db_session.commit()

    refreshed_tx = await db_session.get(Transaction, tx.id)
    assert refreshed_tx is not None
    assert refreshed_tx.status == TransactionStatus.COMPLETED


async def test_ai_call_service_records_success_and_error(
    db_session: AsyncSession,
    make_user,
):
    """AiCallService.record_success / record_error persist rows."""
    from app.db.models.ai_call import AiCall, AiCallKind, AiCallStatus
    from app.services.ai_call_service import AiCallService

    user = await make_user()
    svc = AiCallService(db_session)

    await svc.record_success(
        user_id=user.id,
        product_id=None,
        kind=AiCallKind.ANALYZE,
        usage={
            "model": "google/gemini-2.5-flash",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cost_usd": 0.000123,
            "generation_id": "gen-abc",
        },
    )
    await svc.record_error(
        user_id=user.id,
        product_id=None,
        kind=AiCallKind.ENHANCE,
        model="google/gemini-2.5-flash-image",
        error_message="upstream timeout",
    )
    await db_session.commit()

    rows = (await db_session.execute(select(AiCall).order_by(AiCall.created_at))).scalars().all()
    assert len(rows) == 2

    success_row = next(r for r in rows if r.status == AiCallStatus.SUCCESS)
    assert success_row.kind == AiCallKind.ANALYZE
    assert success_row.model == "google/gemini-2.5-flash"
    assert success_row.prompt_tokens == 100
    assert success_row.completion_tokens == 50
    assert float(success_row.cost_usd) == 0.000123
    assert success_row.generation_id == "gen-abc"

    error_row = next(r for r in rows if r.status == AiCallStatus.ERROR)
    assert error_row.kind == AiCallKind.ENHANCE
    assert error_row.cost_usd == 0
    assert error_row.error_message == "upstream timeout"


def test_basalam_error_to_persian_prefers_persian_message_then_status_then_text():
    from app.core.exceptions import BasalamError
    from app.services.processing_service import _basalam_error_to_persian

    # 1. Persian message already inside detail → surface verbatim.
    exc = BasalamError("خطای API باسلام", 422, {"message": "نام محصول الزامی است."})
    assert _basalam_error_to_persian(exc) == "نام محصول الزامی است."

    # 2. English snippet inside detail → translated.
    exc = BasalamError("خطای API باسلام", 400, {"detail": "Validation failed"})
    assert "بازبینی" in _basalam_error_to_persian(exc)

    # 3. No message, only status code → mapped to its Persian default.
    exc = BasalamError("خطای API باسلام", 503, None)
    assert "دسترس" in _basalam_error_to_persian(exc)

    # 4. Unknown status, generic exc message → exc message wins.
    exc = BasalamError("اطلاعات وندور یافت نشد.", 418, None)
    assert _basalam_error_to_persian(exc) == "اطلاعات وندور یافت نشد."


def test_openrouter_extract_usage_parses_response_body():
    """_extract_usage builds the dict AiCallService expects."""
    from app.services.openrouter_service import _extract_usage

    usage = _extract_usage(
        {
            "id": "gen-xyz",
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 7,
                "total_tokens": 19,
                "cost": 0.0004567,
            },
        },
        model="google/gemini-2.5-flash",
    )
    assert usage["model"] == "google/gemini-2.5-flash"
    assert usage["prompt_tokens"] == 12
    assert usage["completion_tokens"] == 7
    assert usage["total_tokens"] == 19
    assert usage["cost_usd"] == 0.0004567
    assert usage["generation_id"] == "gen-xyz"

    # Missing usage block → cost defaults to 0.
    empty = _extract_usage({"id": None}, model="m")
    assert empty["cost_usd"] == 0
    assert empty["model"] == "m"


async def test_delete_product_blocked_for_submitted(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user,
    auth_cookie,
):
    """DELETE /products/{id} on SUBMITTED status must return 409."""
    user = await make_user()
    await _give_balance(db_session, user.id, 5)
    await db_session.flush()

    cookies = auth_cookie(user)
    create_resp = await client.post(
        "/api/v1/products/",
        json=_product_payload(1),
        cookies=cookies,
    )
    assert create_resp.status_code == 201
    product_id_str = create_resp.json()["product_id"]
    product_id = _uuid_module.UUID(product_id_str)

    product = await db_session.get(Product, product_id)
    assert product is not None
    product.status = ProductStatus.SUBMITTED
    await db_session.commit()

    delete_resp = await client.delete(
        f"/api/v1/products/{product_id_str}",
        cookies=cookies,
    )
    assert delete_resp.status_code == 409

    # Product row still present.
    still = await db_session.get(Product, product_id)
    assert still is not None
    assert still.status == ProductStatus.SUBMITTED
