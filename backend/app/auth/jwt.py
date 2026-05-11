from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import AuthError

ALGORITHM = "HS256"


def encode_session(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    exp = now + timedelta(days=settings.session_ttl_days)
    payload = {"sub": str(user_id), "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(payload, settings.session_secret, algorithm=ALGORITHM)


def decode_session(token: str) -> uuid.UUID:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.session_secret, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise AuthError("توکن نشست نامعتبر است.") from exc
    sub = payload.get("sub")
    if not sub:
        raise AuthError("توکن نشست ناقص است.")
    try:
        return uuid.UUID(sub)
    except ValueError as exc:
        raise AuthError("شناسه کاربر در توکن معتبر نیست.") from exc
