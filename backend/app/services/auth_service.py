from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.crypto import encrypt_token
from app.auth.jwt import encode_session
from app.auth.oauth import build_authorize_url as _build_authorize_url
from app.auth.oauth import exchange_code
from app.core.config import get_settings
from app.core.exceptions import AuthError
from app.db.models.transaction import ReferenceType, TransactionStatus
from app.db.models.user import User
from app.repositories.financial import TransactionRepository
from app.repositories.user import OAuthAccountRepository, UserRepository
from app.utils.logging import LoggerMixin


def _extract_user(payload: Any) -> dict:
    """Extract normalised user fields from the Basalam OAuth token payload.

    Handles both the bridge response shape (data.user) and the direct OpenAPI
    profile shape, returning a flat dict with the keys required for User upsert.
    """
    data = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        return {}
    user = data.get("user") if isinstance(data.get("user"), dict) else data
    vendor = user.get("vendor") if isinstance(user.get("vendor"), dict) else {}
    return {
        "id": user.get("id"),
        "name": user.get("name") or user.get("first_name") or "",
        "username": user.get("user_name") or user.get("username") or "",
        "avatar_url": (user.get("avatar") or {}).get("url") if isinstance(user.get("avatar"), dict) else user.get("avatar_url"),
        "email": user.get("email"),
        "vendor_id": vendor.get("id") if vendor else (user.get("vendor_id")),
    }


class AuthService(LoggerMixin):
    """Encapsulates all authentication business logic for the Basalam OAuth flow.

    The service is HTTP-transport-agnostic: it never sets cookies, issues
    redirects, or constructs HTTP responses.  Those concerns belong to the
    router layer (app/api/v1/auth.py).
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.oauth_repo = OAuthAccountRepository(session)
        self.tx_repo = TransactionRepository(session)

    # ------------------------------------------------------------------
    # OAuth helpers
    # ------------------------------------------------------------------

    def generate_oauth_state(self) -> str:
        """Generate a cryptographically-random CSRF state token."""
        return secrets.token_urlsafe(32)

    def build_authorize_url(self, state: str) -> str:
        """Return the Basalam OAuth authorisation URL for the given state token."""
        return _build_authorize_url(state)

    # ------------------------------------------------------------------
    # Callback flow
    # ------------------------------------------------------------------

    async def complete_oauth_callback(
        self,
        *,
        code: str,
        state_from_query: str,
        state_from_cookie: str | None,
    ) -> tuple[User, str]:
        """Execute the full OAuth callback flow and return (user, jwt_token).

        Steps:
        1. Validate the OAuth state parameter to prevent CSRF.
        2. Exchange the authorisation code for tokens via Basalam.
        3. Extract user fields from the token payload.
        4. Upsert the User row by basalam_user_id.
        5. Upsert the OAuthAccount row (tokens encrypted at rest).
        6. Grant a signup gift deposit for first-time users when configured.
        7. Commit the database transaction.
        8. Mint a signed JWT session token.

        Args:
            code: The authorisation code received from Basalam.
            state_from_query: The ``state`` query parameter from the callback URL.
            state_from_cookie: The ``oauth_state`` cookie value set during login.

        Returns:
            A 2-tuple of (User ORM instance, signed JWT string).

        Raises:
            AuthError: When the state parameters do not match or when Basalam
                returns an unusable response.
        """
        settings = get_settings()

        # Step 1 — CSRF state validation
        if not state_from_cookie or state_from_query != state_from_cookie:
            self.logger.warning(
                "complete_oauth_callback state mismatch received=%s cookie=%s",
                state_from_query[:8] if state_from_query else None,
                state_from_cookie[:8] if state_from_cookie else None,
            )
            raise AuthError("state نامعتبر")

        # Step 2 — Code exchange
        self.logger.debug("complete_oauth_callback exchanging code state=%s", state_from_query[:8])
        tokens = await exchange_code(code)

        # Step 3 — Profile extraction
        profile = _extract_user(tokens.user_data)
        raw_basalam_id = profile.get("id")
        if not raw_basalam_id:
            self.logger.error(
                "complete_oauth_callback no user id in payload user_data=%s",
                tokens.user_data,
            )
            raise AuthError("اطلاعات کاربر از باسلام دریافت نشد")

        basalam_user_id = int(raw_basalam_id)
        name: str = profile.get("name") or ""
        username: str = profile.get("username") or ""
        vendor_id = profile.get("vendor_id")
        avatar_url = profile.get("avatar_url")
        email = profile.get("email")

        # Step 4 — Upsert User
        existing_user = await self.user_repo.get_by_basalam_user_id(basalam_user_id)
        is_new = existing_user is None

        if is_new:
            user = User(
                basalam_user_id=basalam_user_id,
                name=name,
                username=username,
                vendor_id=vendor_id,
                avatar_url=avatar_url,
                email=email,
            )
            self.session.add(user)
            await self.session.flush()
            self.logger.info(
                "complete_oauth_callback new user basalam_user_id=%s user_id=%s",
                basalam_user_id,
                user.id,
            )
        else:
            user = existing_user
            user.name = name
            user.username = username
            user.vendor_id = vendor_id
            if avatar_url is not None:
                user.avatar_url = avatar_url
            self.logger.info(
                "complete_oauth_callback existing user basalam_user_id=%s user_id=%s",
                basalam_user_id,
                user.id,
            )

        # Step 5 — Upsert OAuthAccount (tokens encrypted at rest)
        encrypted_access = encrypt_token(tokens.access_token)
        encrypted_refresh = encrypt_token(tokens.refresh_token) if tokens.refresh_token else None

        expires_at: datetime | None = None
        if tokens.expires_in is not None:
            expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=tokens.expires_in)

        await self.oauth_repo.upsert(
            user_id=user.id,
            provider="basalam",
            access_token_enc=encrypted_access,
            refresh_token_enc=encrypted_refresh,
            expires_at=expires_at,
            scope=tokens.scope,
            raw_payload=tokens.user_data,
        )

        # Step 6 — Signup gift for new users
        if is_new and settings.signup_gift_amount > 0:
            await self.tx_repo.create_deposit(
                user_id=user.id,
                reference_type=ReferenceType.GIFT,
                reference_id=None,
                amount=settings.signup_gift_amount,
                status=TransactionStatus.COMPLETED,
                note="هدیه ثبت‌نام",
            )
            self.logger.info(
                "complete_oauth_callback signup gift user_id=%s amount=%s",
                user.id,
                settings.signup_gift_amount,
            )

        # Step 7 — Commit
        await self.session.commit()
        self.logger.info("complete_oauth_callback login complete user_id=%s", user.id)

        # Step 8 — Mint JWT
        jwt_token = encode_session(user.id)

        return user, jwt_token

    # ------------------------------------------------------------------
    # Profile payload
    # ------------------------------------------------------------------

    async def get_me_payload(self, user: User) -> dict:
        """Build the /me response payload for the given authenticated user.

        Args:
            user: The currently authenticated User ORM instance.

        Returns:
            Dict with keys: id, basalam_user_id, vendor_id, name, username,
            avatar_url, balance.
        """
        balance = await self.tx_repo.compute_balance(user.id)
        self.logger.debug("get_me_payload user_id=%s balance=%s", user.id, balance)
        return {
            "id": user.id,
            "basalam_user_id": user.basalam_user_id,
            "vendor_id": user.vendor_id,
            "name": user.name,
            "username": user.username,
            "avatar_url": user.avatar_url,
            "balance": balance,
        }
