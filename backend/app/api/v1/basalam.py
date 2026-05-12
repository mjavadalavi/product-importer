from __future__ import annotations

import logging
from time import time as _now
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.crypto import decrypt_token
from app.auth.deps import require_user
from app.db.models.user import User
from app.db.session import get_db
from app.repositories.user import OAuthAccountRepository
from app.schemas.basalam import CategoriesResponse
from app.services.basalam_service import BasalamService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/basalam", tags=["basalam"])

_CACHE_TTL = 3600.0

# Keys are (user_id, cache_name); values are (expires_at, cached_value).
_cache: dict[tuple[Any, str], tuple[float, Any]] = {}


def _cache_get(key: tuple[Any, str]) -> Any | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    expires_at, value = entry
    if _now() >= expires_at:
        del _cache[key]
        return None
    return value


def _cache_set(key: tuple[Any, str], value: Any) -> None:
    _cache[key] = (_now() + _CACHE_TTL, value)


async def _basalam_for(user: User, db: AsyncSession) -> BasalamService:
    """Resolve the user's Basalam OAuth token and return a ready BasalamService."""
    oauth_repo = OAuthAccountRepository(db)
    oauth = await oauth_repo.get_for_user(user.id, provider="basalam")
    if oauth is None:
        raise HTTPException(status_code=401, detail="اتصال باسلام موجود نیست.")
    return BasalamService(token=decrypt_token(oauth.access_token_enc))


@router.get("/categories", response_model=CategoriesResponse)
async def get_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> CategoriesResponse:
    logger.info("get_categories user=%s", user.id)

    cache_key = (user.id, "categories")
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.debug("get_categories cache_hit user=%s", user.id)
        return cached

    svc = await _basalam_for(user, db)
    raw = await svc.get_categories()
    flat = svc.flatten_categories(raw)

    response = CategoriesResponse(raw=raw, flat=flat)
    _cache_set(cache_key, response)
    logger.info("get_categories fetched user=%s flat_count=%s", user.id, len(flat))
    return response


@router.get("/categories/{category_id}/attributes")
async def get_category_attributes(
    category_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> Any:
    logger.info("get_category_attributes user=%s category_id=%s", user.id, category_id)

    svc = await _basalam_for(user, db)
    result = await svc.get_category_attributes(category_id, vendor_id=user.vendor_id)
    logger.info("get_category_attributes done user=%s category_id=%s", user.id, category_id)
    return result
