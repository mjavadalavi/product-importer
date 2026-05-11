from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.crypto import encrypt_token
from app.auth.deps import get_current_user, require_user
from app.auth.jwt import encode_session
from app.auth.oauth import exchange_code
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.oauth_account import OAuthAccount
from app.db.models.transaction import ReferenceType, TransactionStatus
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import MeResponse
from app.services import ledger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _extract_user(payload: Any) -> dict:
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


@router.get("/basalam/login")
async def basalam_login() -> RedirectResponse:
    settings = get_settings()
    state = secrets.token_urlsafe(32)

    from app.auth.oauth import build_authorize_url
    authorize_url = build_authorize_url(state)

    response = RedirectResponse(authorize_url, status_code=302)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=600,
    )
    logger.info("basalam_login state=%s", state[:8])
    return response


@router.get("/basalam/callback")
async def basalam_callback(
    code: str,
    state: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    oauth_state: str | None = Cookie(default=None, alias="oauth_state"),
) -> RedirectResponse:
    settings = get_settings()

    if not oauth_state or state != oauth_state:
        logger.warning("basalam_callback state mismatch received=%s cookie=%s", state[:8] if state else None, oauth_state[:8] if oauth_state else None)
        raise HTTPException(status_code=400, detail="state نامعتبر")

    try:
        tokens = await exchange_code(code)
    except Exception as exc:
        logger.error("basalam_callback exchange_code failed: %s", exc)
        raise HTTPException(status_code=502, detail="تبادل کد با باسلام ناموفق بود") from exc

    profile = _extract_user(tokens.user_data)
    basalam_user_id = profile.get("id")
    if not basalam_user_id:
        logger.error("basalam_callback no user id in payload user_data=%s", tokens.user_data)
        raise HTTPException(status_code=502, detail="اطلاعات کاربر از باسلام دریافت نشد")

    basalam_user_id = int(basalam_user_id)
    name: str = profile.get("name") or ""
    username: str = profile.get("username") or ""
    vendor_id = profile.get("vendor_id")
    avatar_url = profile.get("avatar_url")
    email = profile.get("email")

    result = await db.execute(select(User).where(User.basalam_user_id == basalam_user_id))
    existing_user: User | None = result.scalar_one_or_none()

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
        db.add(user)
        await db.flush()
        logger.info("basalam_callback new user basalam_user_id=%s user_id=%s", basalam_user_id, user.id)
    else:
        user = existing_user
        user.name = name
        user.username = username
        user.vendor_id = vendor_id
        if avatar_url is not None:
            user.avatar_url = avatar_url
        logger.info("basalam_callback existing user basalam_user_id=%s user_id=%s", basalam_user_id, user.id)

    expires_at: datetime | None = None
    if tokens.expires_in is not None:
        expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=tokens.expires_in)

    oauth_result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == user.id,
            OAuthAccount.provider == "basalam",
        )
    )
    oauth_account: OAuthAccount | None = oauth_result.scalar_one_or_none()

    encrypted_access = encrypt_token(tokens.access_token)
    encrypted_refresh = encrypt_token(tokens.refresh_token) if tokens.refresh_token else None

    if oauth_account is None:
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider="basalam",
            access_token_enc=encrypted_access,
            refresh_token_enc=encrypted_refresh,
            expires_at=expires_at,
            scope=tokens.scope,
            raw_payload=tokens.user_data,
        )
        db.add(oauth_account)
    else:
        oauth_account.access_token_enc = encrypted_access
        if encrypted_refresh is not None:
            oauth_account.refresh_token_enc = encrypted_refresh
        oauth_account.expires_at = expires_at
        oauth_account.scope = tokens.scope
        oauth_account.raw_payload = tokens.user_data

    if is_new and settings.signup_gift_amount > 0:
        await ledger.deposit(
            db,
            user_id=user.id,
            ref_type=ReferenceType.GIFT,
            ref_id=None,
            amount=settings.signup_gift_amount,
            status=TransactionStatus.COMPLETED,
            note="هدیه ثبت‌نام",
        )
        logger.info("basalam_callback signup gift user_id=%s amount=%s", user.id, settings.signup_gift_amount)

    await db.commit()

    session_token = encode_session(user.id)

    response = RedirectResponse(f"{settings.app_origin}/home", status_code=302)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_days * 86400,
    )
    response.delete_cookie(key="oauth_state")
    logger.info("basalam_callback login complete user_id=%s", user.id)
    return response


@router.get("/me", response_model=MeResponse)
async def me(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> MeResponse:
    balance = await ledger.get_balance(db, user.id)
    return MeResponse(
        id=user.id,
        basalam_user_id=user.basalam_user_id,
        vendor_id=user.vendor_id,
        name=user.name,
        username=user.username,
        avatar_url=user.avatar_url,
        balance=balance,
    )


@router.post("/logout")
async def logout(response: Response) -> JSONResponse:
    settings = get_settings()
    result = JSONResponse({"ok": True})
    result.delete_cookie(key=settings.session_cookie_name)
    logger.info("logout cookie cleared")
    return result
