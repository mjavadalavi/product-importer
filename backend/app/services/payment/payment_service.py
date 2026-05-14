"""Async Python port of product-name's PaymentService.ts.

Thin client around the Shopyaar payment bridge (pay.ejourney.ir / compatible).
Mirrors the TS implementation:

    - createPayment(amount, callback_url, user_phone)
        POST {base}/payments/create
        body: {"amount": ..., "callback_url": ..., "user_phone": ...}

    - verifyPayment(token)
        POST {base}/payments/verify?authority=<token>

Sensitive headers (`x-api-key`) are masked before logging. Network errors,
timeouts and non-2xx responses are normalised into PaymentBridgeError so
callers do not need to deal with httpx internals.

When the bridge is not configured OR `payment_bridge_bypass=True`, both
methods return a deterministic mock response so the rest of the wallet
flow can be exercised end-to-end in development without a live gateway.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional
from urllib.parse import urlencode, urljoin

import httpx

from app.core.config import Settings, get_settings
from app.utils.logging import LoggerMixin


class PaymentBridgeError(Exception):
    """Raised when the upstream payment bridge fails or is unreachable."""

    def __init__(self, message: str, *, status_code: int | None = None, detail: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


def _mask_api_key(value: str | None) -> str | None:
    if not value:
        return value
    if len(value) <= 10:
        return value[:3] + "..."
    return value[:10] + "..."


class PaymentService(LoggerMixin):
    """Stateless wrapper around the payment bridge HTTP API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    # ------------------------------------------------------------------
    # Config-derived properties
    # ------------------------------------------------------------------

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
    def timeout_seconds(self) -> float:
        ms = self._settings.payment_bridge_timeout_ms or 15_000
        return max(ms / 1000.0, 0.1)

    @property
    def enabled(self) -> bool:
        return bool(self._settings.payment_bridge_enabled and self.base_url)

    @property
    def bypass(self) -> bool:
        return bool(self._settings.payment_bridge_bypass) or not self.enabled

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_url(self, pathname: str, params: dict[str, str] | None = None) -> str | None:
        if not self.enabled:
            return None
        base = self.base_url + "/" if not self.base_url.endswith("/") else self.base_url
        url = urljoin(base, pathname.lstrip("/"))
        if params:
            sep = "&" if "?" in url else "?"
            url = url + sep + urlencode(params)
        return url

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def _fetch_json(
        self,
        url: str | None,
        *,
        method: str = "POST",
        body: dict[str, Any] | None = None,
    ) -> Any:
        if not url:
            raise PaymentBridgeError("Payment bridge is not configured")

        headers = self._build_headers()
        log_headers = {**headers}
        if log_headers.get("x-api-key"):
            log_headers["x-api-key"] = _mask_api_key(log_headers["x-api-key"]) or ""

        body_text = json.dumps(body, ensure_ascii=False) if body is not None else None

        self.logger.info(
            "Payment bridge request",
            extra={
                "url": url,
                "method": method,
                "body": body_text,
                "headers": log_headers,
            },
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    content=body_text.encode("utf-8") if body_text is not None else None,
                )
        except httpx.TimeoutException as exc:
            self.logger.error(
                "Payment bridge request timeout url=%s timeout_ms=%s",
                url,
                self._settings.payment_bridge_timeout_ms,
            )
            raise PaymentBridgeError("Payment gateway timeout - please try again") from exc
        except httpx.HTTPError as exc:
            self.logger.error("Payment bridge connection failed url=%s error=%s", url, exc)
            raise PaymentBridgeError(f"Payment bridge unreachable: {exc}") from exc

        raw_body = response.text or ""

        log_data = {
            "status": response.status_code,
            "responseBody": raw_body[:2000],
            "contentType": response.headers.get("content-type"),
        }

        if response.is_error:
            self.logger.error("Payment bridge error response %s", log_data)
            error_message = raw_body
            parsed_detail: Any = None
            if raw_body:
                try:
                    parsed_detail = json.loads(raw_body)
                    if isinstance(parsed_detail, dict):
                        error_message = (
                            parsed_detail.get("message")
                            or parsed_detail.get("error")
                            or raw_body
                        )
                except json.JSONDecodeError:
                    pass
            raise PaymentBridgeError(
                f"Payment bridge HTTP {response.status_code}: {error_message}",
                status_code=response.status_code,
                detail=parsed_detail if parsed_detail is not None else raw_body,
            )

        self.logger.info("Payment bridge success response %s", log_data)
        if not raw_body:
            return None
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise PaymentBridgeError(
                "Payment bridge response was not valid JSON",
                status_code=response.status_code,
                detail=raw_body,
            ) from exc

    # ------------------------------------------------------------------
    # Public API (mirrors the TS PaymentService)
    # ------------------------------------------------------------------

    async def create_payment(
        self,
        *,
        amount: int,
        callback_url: Optional[str] = None,
        user_phone: Optional[str] = None,
    ) -> dict[str, Any]:
        """Open a new payment on the bridge.

        Returns the bridge's JSON response (typically containing a token and
        the redirect URL). In bypass mode returns a deterministic mock.
        """
        if self.bypass:
            token = f"mock-{int(time.time() * 1000)}"
            self.logger.warning(
                "Payment bridge bypass enabled; issuing mock payment token amount=%s",
                amount,
            )
            return {
                "status": True,
                "token": token,
                "url": callback_url or f"{self.callback_url}/mock/{token}",
                "bypass": True,
            }

        url = self._build_url("/payments/create")
        body: dict[str, Any] = {
            "amount": amount,
            "callback_url": callback_url,
            "user_phone": user_phone,
        }
        return await self._fetch_json(url, method="POST", body=body)

    async def verify_payment(self, *, token: Optional[str] = None) -> dict[str, Any]:
        """Verify a payment by its token (`authority`).

        Returns the bridge's JSON response (typically `{status, ref_id, ...}`).
        In bypass mode returns a deterministic mock.
        """
        if self.bypass:
            self.logger.warning(
                "Payment bridge bypass enabled; auto-verifying payment token=%s",
                token,
            )
            return {
                "status": True,
                "ref_id": f"mock-ref-{int(time.time() * 1000)}",
                "bypass": True,
            }

        params = {"authority": token} if token else None
        url = self._build_url("/payments/verify", params=params)
        return await self._fetch_json(url, method="POST")
