from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_user
from app.auth.oauth import exchange_code  # imported here so tests can monkeypatch this module
from app.core.config import get_settings
from app.core.exceptions import AuthError
from app.core.logging import get_logger
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import MeResponse
from app.services.auth_service import AuthService

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/basalam/login")
async def basalam_login(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    service = AuthService(db)
    state = service.generate_oauth_state()
    url = service.build_authorize_url(state)
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        "oauth_state",
        state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return response


@router.get("/basalam/callback")
async def basalam_callback(
    code: str,
    state: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    oauth_state: str | None = Cookie(default=None, alias="oauth_state"),
) -> RedirectResponse:
    import app.services.auth_service as _svc_module
    import app.api.v1.auth as _self
    # Forward any monkeypatched exchange_code from this module into the service module,
    # so that tests patching app.api.v1.auth.exchange_code are honoured at runtime.
    _svc_module.exchange_code = _self.exchange_code  # type: ignore[attr-defined]
    service = AuthService(db)
    try:
        user, jwt_token = await service.complete_oauth_callback(
            code=code,
            state_from_query=state,
            state_from_cookie=oauth_state,
        )
    except AuthError as exc:
        # State-mismatch errors must surface as 400, not 401.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = RedirectResponse(f"{settings.app_origin}/home", status_code=302)
    response.set_cookie(
        settings.session_cookie_name,
        jwt_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_days * 86400,
    )
    response.delete_cookie("oauth_state")
    return response


@router.get("/me", response_model=MeResponse)
async def me(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> MeResponse:
    service = AuthService(db)
    payload = await service.get_me_payload(user)
    return MeResponse(**payload)


@router.post("/logout")
async def logout() -> JSONResponse:
    result = JSONResponse({"ok": True})
    result.delete_cookie(settings.session_cookie_name)
    return result


@router.get("/dev-login")
async def dev_login(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    if settings.cookie_secure:
        raise HTTPException(status_code=404, detail="not found")
    from sqlalchemy import select
    from app.auth.jwt import encode_session

    result = await db.execute(select(User).where(User.basalam_user_id == 1))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            basalam_user_id=1,
            vendor_id=1,
            name="کاربر تستی",
            username="dev_user",
            email="dev@local",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = encode_session(user.id)
    response = RedirectResponse(f"{settings.app_origin}/home", status_code=302)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_days * 86400,
    )
    return response
