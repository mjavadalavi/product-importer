"""
User repositories: UserRepository and OAuthAccountRepository.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.oauth_account import OAuthAccount
from app.db.models.user import User
from app.repositories.base import BaseRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class UserRepository(BaseRepository[User]):
    """Repository for User model operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def get_by_basalam_user_id(self, basalam_user_id: int) -> User | None:
        """
        Look up a User by their Basalam platform user ID.

        Returns None when no matching row exists.
        """
        query = select(self.model).where(
            self.model.basalam_user_id == basalam_user_id,
        )
        result = await self.session.execute(query)
        user = result.scalar_one_or_none()
        logger.debug(
            "get_by_basalam_user_id: basalam_user_id=%s found=%s",
            basalam_user_id,
            user is not None,
        )
        return user

    async def get_by_username(self, username: str) -> User | None:
        """
        Look up a User by their unique username.

        Returns None when no matching row exists.
        """
        query = select(self.model).where(
            self.model.username == username,
        )
        result = await self.session.execute(query)
        user = result.scalar_one_or_none()
        logger.debug(
            "get_by_username: username=%s found=%s",
            username,
            user is not None,
        )
        return user


class OAuthAccountRepository(BaseRepository[OAuthAccount]):
    """Repository for OAuthAccount model operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OAuthAccount, session)

    async def get_for_user(
        self, user_id: UUID, provider: str = "basalam"
    ) -> OAuthAccount | None:
        """
        Retrieve the OAuthAccount for a given user and OAuth provider.

        Returns None when no matching row exists.
        """
        query = select(self.model).where(
            self.model.user_id == user_id,
            self.model.provider == provider,
        )
        result = await self.session.execute(query)
        account = result.scalar_one_or_none()
        logger.debug(
            "get_for_user: user_id=%s provider=%s found=%s",
            user_id,
            provider,
            account is not None,
        )
        return account

    async def upsert(
        self,
        *,
        user_id: UUID,
        provider: str,
        access_token_enc: str,
        refresh_token_enc: str | None,
        expires_at: datetime | None,
        scope: str | None,
        raw_payload: dict | None,
    ) -> OAuthAccount:
        """
        Insert or update the OAuthAccount identified by (user_id, provider).

        If a row already exists it is updated in-place; otherwise a new row is
        created.  The session is flushed so the caller can rely on the
        returned object having a populated primary key, but the transaction is
        NOT committed here — that is the caller's responsibility.

        Args:
            user_id: UUID of the owning User row.
            provider: OAuth provider name (e.g. "basalam").
            access_token_enc: Encrypted access token string.
            refresh_token_enc: Encrypted refresh token string, or None.
            expires_at: Token expiry timestamp (tz-aware), or None.
            scope: Space-separated scope string, or None.
            raw_payload: Raw OAuth response dict for auditing, or None.

        Returns:
            The persisted OAuthAccount instance (refreshed after flush).
        """
        existing = await self.get_for_user(user_id, provider)

        if existing is not None:
            existing.access_token_enc = access_token_enc
            existing.refresh_token_enc = refresh_token_enc
            existing.expires_at = expires_at
            existing.scope = scope
            existing.raw_payload = raw_payload
            self.db.add(existing)
            await self.db.flush()
            await self.db.refresh(existing)
            logger.info(
                "upsert OAuthAccount: updated user_id=%s provider=%s id=%s",
                user_id,
                provider,
                existing.id,
            )
            return existing

        new_account = OAuthAccount(
            id=uuid.uuid4(),
            user_id=user_id,
            provider=provider,
            access_token_enc=access_token_enc,
            refresh_token_enc=refresh_token_enc,
            expires_at=expires_at,
            scope=scope,
            raw_payload=raw_payload,
        )
        self.db.add(new_account)
        await self.db.flush()
        await self.db.refresh(new_account)
        logger.info(
            "upsert OAuthAccount: created user_id=%s provider=%s id=%s",
            user_id,
            provider,
            new_account.id,
        )
        return new_account
