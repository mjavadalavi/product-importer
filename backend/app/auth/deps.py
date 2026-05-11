from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_session
from app.core.config import get_settings
from app.core.exceptions import AuthError
from app.db.models.user import User
from app.db.session import get_db


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    session_cookie: str | None = Cookie(default=None, alias="pi_session"),
) -> User | None:
    settings = get_settings()
    raw = session_cookie
    if not raw:
        return None
    try:
        user_id = decode_session(raw)
    except AuthError:
        return None
    result = await db.get(User, user_id)
    return result


async def require_user(
    user: Annotated[User | None, Depends(get_current_user)],
) -> User:
    if user is None:
        raise AuthError()
    return user
