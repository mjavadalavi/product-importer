from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.exceptions import AuthError
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BasalamTokens:
    access_token: str
    refresh_token: str | None
    expires_in: int | None
    scope: str | None
    user_data: dict[str, Any]
    vendor_data: dict[str, Any]


def build_authorize_url(state: str) -> str:
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.basalam_client_id,
        "redirect_uri": settings.basalam_redirect_uri,
        "scope": settings.basalam_scopes,
        "state": state,
    }
    return f"{settings.basalam_authorize_url}?{urlencode(params)}"


async def exchange_code(code: str) -> BasalamTokens:
    settings = get_settings()

    if settings.basalam_bridge_url:
        return await _exchange_via_bridge(code, settings)
    return await _exchange_direct(code, settings)


async def refresh_tokens(refresh_token: str) -> BasalamTokens:
    settings = get_settings()

    if settings.basalam_bridge_url:
        return await _refresh_via_bridge(refresh_token, settings)
    return await _refresh_direct(refresh_token, settings)


async def fetch_profile(access_token: str) -> dict[str, Any]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(
                f"{settings.basalam_openapi_base}/v1/users/me",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise AuthError("دریافت پروفایل کاربر ناموفق بود.") from exc
        if response.status_code >= 400:
            raise AuthError(f"خطای دریافت پروفایل: {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise AuthError("پاسخ پروفایل JSON معتبر نبود.") from exc


async def _exchange_via_bridge(code: str, settings: Any) -> BasalamTokens:
    logger.info("exchanging OAuth code via bridge")
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.post(
                f"{settings.basalam_bridge_url}/basalam/connect",
                json={"code": code},
                headers={"x-api-key": settings.basalam_bridge_api_key, "Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise AuthError("اتصال به bridge باسلام ناموفق بود.") from exc
        if response.status_code >= 400:
            raise AuthError(f"خطای bridge باسلام: {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise AuthError("پاسخ bridge JSON معتبر نبود.") from exc

    access_token = data.get("access_token") or ""
    if not access_token:
        raise AuthError("access_token از bridge دریافت نشد.")

    user_data = data.get("user") or {}
    vendor_data = data.get("vendor") or {}
    return BasalamTokens(
        access_token=access_token,
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in"),
        scope=data.get("scope"),
        user_data=user_data,
        vendor_data=vendor_data,
    )


async def _exchange_direct(code: str, settings: Any) -> BasalamTokens:
    logger.info("exchanging OAuth code directly")
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            token_response = await client.post(
                settings.basalam_token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": settings.basalam_client_id,
                    "client_secret": settings.basalam_client_secret,
                    "redirect_uri": settings.basalam_redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise AuthError("دریافت توکن از باسلام ناموفق بود.") from exc
        if token_response.status_code >= 400:
            raise AuthError(f"خطای توکن باسلام: {token_response.status_code}")
        try:
            token_data = token_response.json()
        except ValueError as exc:
            raise AuthError("پاسخ توکن JSON معتبر نبود.") from exc

    access_token = token_data.get("access_token") or ""
    if not access_token:
        raise AuthError("access_token از باسلام دریافت نشد.")

    user_data = await fetch_profile(access_token)
    return BasalamTokens(
        access_token=access_token,
        refresh_token=token_data.get("refresh_token"),
        expires_in=token_data.get("expires_in"),
        scope=token_data.get("scope"),
        user_data=user_data,
        vendor_data={},
    )


async def _refresh_via_bridge(refresh_token: str, settings: Any) -> BasalamTokens:
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.post(
                f"{settings.basalam_bridge_url}/basalam/refresh",
                json={"refresh_token": refresh_token},
                headers={"x-api-key": settings.basalam_bridge_api_key, "Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise AuthError("refresh via bridge ناموفق بود.") from exc
        if response.status_code >= 400:
            raise AuthError(f"خطای refresh bridge: {response.status_code}")
        data = response.json()

    access_token = data.get("access_token") or ""
    if not access_token:
        raise AuthError("access_token از refresh bridge دریافت نشد.")
    return BasalamTokens(
        access_token=access_token,
        refresh_token=data.get("refresh_token", refresh_token),
        expires_in=data.get("expires_in"),
        scope=data.get("scope"),
        user_data=data.get("user") or {},
        vendor_data=data.get("vendor") or {},
    )


async def _refresh_direct(refresh_token: str, settings: Any) -> BasalamTokens:
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.post(
                settings.basalam_token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": settings.basalam_client_id,
                    "client_secret": settings.basalam_client_secret,
                },
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise AuthError("refresh توکن ناموفق بود.") from exc
        if response.status_code >= 400:
            raise AuthError(f"خطای refresh: {response.status_code}")
        data = response.json()

    access_token = data.get("access_token") or ""
    if not access_token:
        raise AuthError("access_token از refresh دریافت نشد.")
    user_data = await fetch_profile(access_token)
    return BasalamTokens(
        access_token=access_token,
        refresh_token=data.get("refresh_token", refresh_token),
        expires_in=data.get("expires_in"),
        scope=data.get("scope"),
        user_data=user_data,
        vendor_data={},
    )
