"""Common types, Protocol and HTTP adapter base shared by payment adapters."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings, get_settings
from app.utils.logging import LoggerMixin


class PaymentBridgeError(Exception):
    """Raised when an upstream payment gateway fails or is unreachable."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class CreatePaymentResult:
    """Outcome of opening a new payment on a gateway.

    `token` is the value the caller persists and later passes to
    `verify_payment`. `url` is the redirect target shown to the user.
    `raw` is the upstream response for debugging; do not branch on it.
    """

    token: str
    url: str
    bypass: bool = False
    reference_id: str | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class VerifyPaymentResult:
    """Outcome of verifying a payment after callback."""

    success: bool
    ref_id: str | None = None
    bypass: bool = False
    raw: dict[str, Any] | None = None


class PaymentBridge(Protocol):
    """Unified interface for payment-gateway adapters.

    Implementations:
      - ShopyaarPaymentService (pay.ejourney.ir compatible bridge)
      - BasalamPaymentService  (Basalam OpenAPI /v1/pay/* gateway)
    """

    async def create_payment(
        self,
        *,
        amount: int,
        callback_url: str | None = None,
        description: str | None = None,
        user_phone: str | None = None,
    ) -> CreatePaymentResult: ...

    async def verify_payment(self, *, token: str) -> VerifyPaymentResult: ...


def mask_secret(value: str | None) -> str | None:
    """Mask a sensitive header value before logging."""
    if not value:
        return value
    if len(value) <= 10:
        return value[:3] + "..."
    return value[:10] + "..."


class HttpAdapterBase(LoggerMixin):
    """Shared HTTP plumbing for payment adapters.

    Subclasses provide:
      * `provider_name` (str) — used in log/error prefixes
      * `_sensitive_header_keys` (set[str]) — header keys to mask
      * adapter-specific create/verify methods that call `_fetch_json`.
    """

    provider_name: str = "payment"
    _sensitive_header_keys: frozenset[str] = frozenset()

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def timeout_seconds(self) -> float:
        ms = self._settings.payment_bridge_timeout_ms or 15_000
        return max(ms / 1000.0, 0.1)

    def _mask_headers(self, headers: dict[str, str]) -> dict[str, str]:
        masked = dict(headers)
        for key in self._sensitive_header_keys:
            if key in masked and masked[key]:
                masked[key] = mask_secret(masked[key]) or ""
        return masked

    async def _fetch_json(
        self,
        url: str,
        *,
        method: str = "POST",
        headers: dict[str, str],
        body: dict[str, Any] | None = None,
    ) -> Any:
        if not url:
            raise PaymentBridgeError(f"{self.provider_name} gateway is not configured")

        body_text = json.dumps(body, ensure_ascii=False) if body is not None else None
        self.logger.info(
            "%s request method=%s url=%s body=%s headers=%s",
            self.provider_name, method, url, body_text, self._mask_headers(headers),
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
                "%s timeout url=%s timeout_ms=%s",
                self.provider_name, url, self._settings.payment_bridge_timeout_ms,
            )
            raise PaymentBridgeError(
                f"{self.provider_name} gateway timeout - please try again",
            ) from exc
        except httpx.HTTPError as exc:
            self.logger.error(
                "%s connection failed url=%s error=%s",
                self.provider_name, url, exc,
            )
            raise PaymentBridgeError(
                f"{self.provider_name} gateway unreachable: {exc}",
            ) from exc

        raw = response.text or ""
        parsed: Any = None
        if raw:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None

        log_data = {
            "provider": self.provider_name,
            "status": response.status_code,
            "responseBody": raw[:2000],
            "contentType": response.headers.get("content-type"),
        }

        if response.is_error:
            self.logger.error("%s error response %s", self.provider_name, log_data)
            message = extract_error_message(parsed, raw)
            raise PaymentBridgeError(
                f"{self.provider_name} gateway HTTP {response.status_code}: {message}",
                status_code=response.status_code,
                detail=parsed if parsed is not None else raw,
            )

        self.logger.info("%s success response %s", self.provider_name, log_data)
        if not raw:
            return None
        if parsed is None:
            raise PaymentBridgeError(
                f"{self.provider_name} gateway response was not valid JSON",
                status_code=response.status_code,
                detail=raw,
            )
        return parsed


def extract_error_message(parsed: Any, raw: str) -> str:
    """Pull the most-useful human-readable error message out of a gateway body."""
    if isinstance(parsed, dict):
        msg = parsed.get("message") or parsed.get("error")
        if isinstance(msg, str) and msg.strip():
            return msg
        detail = parsed.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail
        if isinstance(detail, list) and detail:
            first = detail[0]
            if isinstance(first, dict):
                inner = first.get("msg") or first.get("message")
                if isinstance(inner, str) and inner.strip():
                    return inner
    return raw or ""
