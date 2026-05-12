"""
Centralised FastAPI dependencies for v1 routes.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_session
from app.core.exceptions import AuthError
from app.db.models.user import User
from app.db.session import get_db

__all__ = ["get_db", "get_current_user", "require_user"]


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    session_cookie: str | None = Cookie(default=None, alias="pi_session"),
) -> User | None:
    """Return the current User if a valid session cookie is present, else None."""
    if not session_cookie:
        return None
    try:
        user_id = decode_session(session_cookie)
    except AuthError:
        return None
    return await db.get(User, user_id)


async def require_user(
    user: Annotated[User | None, Depends(get_current_user)],
) -> User:
    """Like get_current_user but raises 401 when no user is logged in."""
    if user is None:
        raise AuthError()
    return user
