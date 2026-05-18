"""Adapter for the Shopyaar payment bridge (pay.ejourney.ir compatible).

    - create_payment(amount, callback_url, user_phone)
        POST {base}/payments/create
        body: {"amount": ..., "callback_url": ..., "user_phone": ...}

    - verify_payment(token)
        POST {base}/payments/verify?authority=<token>

When the bridge is not configured OR `payment_bridge_bypass=True`, both
methods return deterministic mock results so the wallet flow can be
exercised end-to-end without a live gateway.
"""
from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlencode, urljoin

from app.core.config import Settings
from app.services.payment.base import (
    CreatePaymentResult,
    HttpAdapterBase,
    PaymentBridgeError,
    VerifyPaymentResult,
)

API_KEY_HEADER = "x-api-key"


class ShopyaarPaymentService(HttpAdapterBase):
    """Stateless wrapper around the Shopyaar payment bridge HTTP API."""

    provider_name = "shopyaar-pay"
    _sensitive_header_keys = frozenset({API_KEY_HEADER})

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__(settings)

    @property
    def base_url(self) -> str:
        return (self._settings.payment_bridge_url or "").rstrip("/")

    @property
    def api_key(self) -> str:
        return self._settings.payment_bridge_api_key or ""

    @property
    def callback_url(self) -> str:
        return self._settings.payment_bridge_callback_url or ""

    @property
    def enabled(self) -> bool:
        return bool(self._settings.payment_bridge_enabled and self.base_url)

    @property
    def bypass(self) -> bool:
        return bool(self._settings.payment_bridge_bypass)

    def _ensure_ready(self) -> None:
        if self.bypass:
            return
        if not self.enabled:
            raise PaymentBridgeError(
                "Shopyaar payment bridge is not configured "
                "(set PAYMENT_BRIDGE_URL and PAYMENT_BRIDGE_ENABLED=true, "
                "or PAYMENT_BRIDGE_BYPASS=true for dev/mock).",
            )

    def _build_url(self, pathname: str, params: dict[str, str] | None = None) -> str:
        if not self.enabled:
            return ""
        base = self.base_url + "/" if not self.base_url.endswith("/") else self.base_url
        url = urljoin(base, pathname.lstrip("/"))
        if params:
            sep = "&" if "?" in url else "?"
            url = url + sep + urlencode(params)
        return url

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers[API_KEY_HEADER] = self.api_key
        return headers

    async def create_payment(
        self,
        *,
        amount: int,
        callback_url: str | None = None,
        description: str | None = None,
        user_phone: str | None = None,
    ) -> CreatePaymentResult:
        cb = callback_url or self.callback_url or None

        if self.bypass:
            token = f"mock-{int(time.time() * 1000)}"
            self.logger.warning(
                "Shopyaar pay bypass: issuing mock token amount=%s", amount,
            )
            return CreatePaymentResult(
                token=token,
                url=cb or f"about:blank#mock/{token}",
                bypass=True,
            )

        self._ensure_ready()
        url = self._build_url("/payments/create")
        body: dict[str, Any] = {
            "amount": int(amount),
            "callback_url": cb,
            "user_phone": user_phone,
        }
        data = await self._fetch_json(
            url, method="POST", headers=self._build_headers(), body=body,
        )
        if not isinstance(data, dict):
            raise PaymentBridgeError(
                "Shopyaar bridge response was not an object", detail=data,
            )

        token = data.get("token")
        pay_url = data.get("url")
        if not token or not pay_url:
            raise PaymentBridgeError(
                "Shopyaar bridge response missing token or url", detail=data,
            )

        return CreatePaymentResult(
            token=str(token),
            url=str(pay_url),
            bypass=bool(data.get("bypass")),
            raw=data,
        )

    async def verify_payment(self, *, token: str) -> VerifyPaymentResult:
        if not token:
            raise PaymentBridgeError("verify_payment requires a token")
        if self.bypass:
            self.logger.warning(
                "Shopyaar pay bypass: auto-verifying token=%s", token,
            )
            return VerifyPaymentResult(
                success=True,
                ref_id=f"mock-ref-{int(time.time() * 1000)}",
                bypass=True,
            )

        self._ensure_ready()
        url = self._build_url("/payments/verify", params={"authority": token})
        data = await self._fetch_json(
            url, method="POST", headers=self._build_headers(),
        )
        if not isinstance(data, dict):
            raise PaymentBridgeError(
                "Shopyaar bridge verify response was not an object", detail=data,
            )

        return VerifyPaymentResult(
            success=bool(data.get("status")),
            ref_id=str(data["ref_id"]) if data.get("ref_id") else None,
            bypass=bool(data.get("bypass")),
            raw=data,
        )
