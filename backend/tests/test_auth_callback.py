"""
Integration tests for the auth endpoints: /api/v1/auth/basalam/callback and /api/v1/auth/me.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.oauth import BasalamTokens
from app.core.config import get_settings
from app.db.models.oauth_account import OAuthAccount
from app.db.models.transaction import GeneralType, ReferenceType, Transaction, TransactionStatus
from app.db.models.user import User
from app.services import ledger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tokens(
    basalam_user_id: int = 12345,
    vendor_id: int = 999,
    name: str = "احمد",
    username: str = "ahmad",
) -> BasalamTokens:
    return BasalamTokens(
        access_token="atk",
        refresh_token="rtk",
        expires_in=3600,
        scope=None,
        user_data={
            "id": basalam_user_id,
            "name": name,
            "user_name": username,
            "vendor": {"id": vendor_id},
        },
        vendor_data={},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_callback_state_mismatch_returns_400(client: AsyncClient):
    """If the state param does not match the oauth_state cookie, return 400."""
    response = await client.get(
        "/api/v1/auth/basalam/callback",
        params={"code": "somecode", "state": "wrong-state"},
        cookies={"oauth_state": "correct-state"},
    )
    assert response.status_code == 400


async def test_callback_success_creates_user_and_cookie(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    """
    A valid callback with a matching state should:
    - Create a User row with the correct basalam_user_id and vendor_id.
    - Create an OAuthAccount with an *encrypted* access token (not plaintext).
    - Redirect to {app_origin}/home.
    - Set the session cookie.
    """
    state = "test-state-abc123"
    tokens = _make_tokens(basalam_user_id=12345, vendor_id=999)

    # Patch exchange_code so no real HTTP call is made.
    import app.api.v1.auth as _auth_module
    async def _fake_exchange(code: str) -> BasalamTokens:
        return tokens

    monkeypatch.setattr(_auth_module, "exchange_code", _fake_exchange)

    response = await client.get(
        "/api/v1/auth/basalam/callback",
        params={"code": "authcode", "state": state},
        cookies={"oauth_state": state},
    )

    assert response.status_code == 302
    settings = get_settings()
    assert response.headers["location"].startswith(f"{settings.app_origin}/home")
    assert settings.session_cookie_name in response.cookies

    # Verify the User was created.
    result = await db_session.execute(
        select(User).where(User.basalam_user_id == 12345)
    )
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.vendor_id == 999

    # Verify OAuthAccount was created with encrypted (not plain) token.
    oauth_result = await db_session.execute(
        select(OAuthAccount).where(OAuthAccount.user_id == user.id)
    )
    oauth = oauth_result.scalar_one_or_none()
    assert oauth is not None
    assert oauth.access_token_enc != "atk"  # must be encrypted


async def test_callback_signup_gift_creates_completed_deposit(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    """
    When signup_gift_amount > 0, a completed DEPOSIT GIFT transaction should
    be created for the new user.
    """
    # Patch settings to set gift amount = 5.
    get_settings.cache_clear()
    original_settings = get_settings()
    monkeypatch.setattr(original_settings, "signup_gift_amount", 5)

    state = "gift-state-xyz"
    tokens = _make_tokens(basalam_user_id=77777, vendor_id=888, username="giftuser")

    import app.api.v1.auth as _auth_module
    async def _fake_exchange(code: str) -> BasalamTokens:
        return tokens

    monkeypatch.setattr(_auth_module, "exchange_code", _fake_exchange)

    response = await client.get(
        "/api/v1/auth/basalam/callback",
        params={"code": "giftcode", "state": state},
        cookies={"oauth_state": state},
    )
    assert response.status_code == 302

    # Verify User created.
    user_result = await db_session.execute(
        select(User).where(User.basalam_user_id == 77777)
    )
    user = user_result.scalar_one_or_none()
    assert user is not None

    # Verify COMPLETED DEPOSIT GIFT transaction with amount=5.
    tx_result = await db_session.execute(
        select(Transaction).where(
            Transaction.user_id == user.id,
            Transaction.general_type == GeneralType.DEPOSIT,
            Transaction.reference_type == ReferenceType.GIFT,
            Transaction.status == TransactionStatus.COMPLETED,
        )
    )
    tx = tx_result.scalar_one_or_none()
    assert tx is not None
    assert int(tx.amount) == 5


async def test_me_requires_auth(client: AsyncClient):
    """GET /api/v1/auth/me without a session cookie must return 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_returns_balance(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user,
    auth_cookie,
):
    """
    GET /api/v1/auth/me with a valid session cookie should return the user's
    settled balance.
    """
    user = await make_user(basalam_user_id=55555)

    # Create a completed deposit of 7 directly in the DB session.
    await ledger.deposit(
        db_session,
        user_id=user.id,
        ref_type=ReferenceType.GIFT,
        ref_id=None,
        amount=7,
        status=TransactionStatus.COMPLETED,
    )
    await db_session.flush()

    cookies = auth_cookie(user)
    response = await client.get("/api/v1/auth/me", cookies=cookies)

    assert response.status_code == 200
    data = response.json()
    assert data["balance"] == 7
    assert data["basalam_user_id"] == 55555
