"""Adapter for the Basalam OpenAPI Gateway /v1/pay/* endpoints.

  - create_payment(...)
      POST {basalam_openapi_base}/v1/pay/pre-transactions
      body: { reference_id, amount, description?, callback_url }
      response: { hash_id, pay_url, order, expired_at, gateway, pay_methods }
      → returns CreatePaymentResult(token=hash_id, url=pay_url, ...)

  - verify_payment(token=hash_id)
      POST {basalam_openapi_base}/v1/pay/transactions/{hash_id}/verify
      response: TransactionPublicResource { status: {id, slug, title}, ... }
      → success when status.id == 3 OR slug == "success".

Auth: header `X-Gateway-Secret: <basalam_pay_gateway_secret>`.

A 422 on verify with the canonical "already verified" signal is mapped to
success (idempotent retries after a missed callback). The detection is
deliberately narrow: it requires either `status.slug == "success"` /
`status.id == 3` inside the structured error envelope, OR an explicit
"already verified"-style phrase in the message. Anything else surfaces
as `PaymentBridgeError`.
"""
from __future__ import annotations

import time
import uuid
from typing import Any
from urllib.parse import quote, urljoin

from app.core.config import Settings
from app.services.payment.base import (
    CreatePaymentResult,
    HttpAdapterBase,
    PaymentBridgeError,
    VerifyPaymentResult,
)

GATEWAY_HEADER = "X-Gateway-Secret"
STATUS_ID_SUCCESS = 3
STATUS_SLUG_SUCCESS = "success"

ALREADY_VERIFIED_PHRASES = (
    "already verified",
    "تایید قبلی",
    "تأیید قبلی",
)


class BasalamPaymentService(HttpAdapterBase):
    """Stateless wrapper around the Basalam OpenAPI pay endpoints."""

    provider_name = "basalam-pay"
    _sensitive_header_keys = frozenset({GATEWAY_HEADER})

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__(settings)

    @property
    def base_url(self) -> str:
        return (self._settings.basalam_openapi_base or "").rstrip("/")

    @property
    def gateway_secret(self) -> str:
        return self._settings.basalam_pay_gateway_secret or ""

    @property
    def callback_url(self) -> str:
        return self._settings.payment_bridge_callback_url or ""

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.gateway_secret)

    @property
    def bypass(self) -> bool:
        return bool(self._settings.payment_bridge_bypass) or not self.enabled

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.gateway_secret:
            headers[GATEWAY_HEADER] = self.gateway_secret
        return headers

    def _url(self, path: str) -> str:
        return urljoin(self.base_url + "/", path.lstrip("/"))

    async def create_payment(
        self,
        *,
        amount: int,
        callback_url: str | None = None,
        description: str | None = None,
        user_phone: str | None = None,
    ) -> CreatePaymentResult:
        ref = uuid.uuid4().hex

        if self.bypass:
            token = f"mock-{int(time.time() * 1000)}"
            self.logger.warning(
                "Basalam pay bypass: issuing mock token amount=%s ref=%s",
                amount, ref,
            )
            return CreatePaymentResult(
                token=token,
                url=callback_url or self.callback_url or f"about:blank#mock/{token}",
                bypass=True,
                reference_id=ref,
            )

        cb = callback_url or self.callback_url
        if not cb:
            raise PaymentBridgeError("callback_url is required for Basalam pay create")

        body: dict[str, Any] = {
            "reference_id": ref,
            "amount": int(amount),
            "callback_url": cb,
        }
        if description:
            body["description"] = description

        data = await self._fetch_json(
            self._url("/v1/pay/pre-transactions"),
            method="POST",
            headers=self._headers(),
            body=body,
        )
        if not isinstance(data, dict):
            raise PaymentBridgeError(
                "Basalam pay create response was not an object", detail=data,
            )
        hash_id = data.get("hash_id")
        pay_url = data.get("pay_url")
        if not hash_id or not pay_url:
            raise PaymentBridgeError(
                "Basalam pay create response missing hash_id or pay_url",
                detail=data,
            )
        return CreatePaymentResult(
            token=str(hash_id),
            url=str(pay_url),
            bypass=False,
            reference_id=ref,
            raw=data,
        )

    async def verify_payment(self, *, token: str) -> VerifyPaymentResult:
        if not token:
            raise PaymentBridgeError("verify_payment requires a token (hash_id)")

        if self.bypass:
            return VerifyPaymentResult(
                success=True,
                ref_id=f"mock-ref-{int(time.time() * 1000)}",
                bypass=True,
            )

        safe_token = quote(token, safe="")
        path = f"/v1/pay/transactions/{safe_token}/verify"

        try:
            data = await self._fetch_json(
                self._url(path), method="POST", headers=self._headers(),
            )
        except PaymentBridgeError as exc:
            if exc.status_code == 422 and _is_already_verified(exc):
                self.logger.info(
                    "Basalam pay verify: upstream reports already verified token=%s",
                    token,
                )
                raw = exc.detail if isinstance(exc.detail, dict) else None
                return VerifyPaymentResult(
                    success=True,
                    ref_id=_extract_bank_ref(raw) or token,
                    bypass=False,
                    raw=raw,
                )
            raise

        if not isinstance(data, dict):
            raise PaymentBridgeError(
                "Basalam pay verify response was not an object", detail=data,
            )

        success = _is_status_success(data.get("status"))
        ref_id = _extract_bank_ref(data) or str(data.get("hash_id") or "") or None
        return VerifyPaymentResult(
            success=bool(success),
            ref_id=ref_id,
            bypass=False,
            raw=data,
        )


def _is_status_success(status_obj: Any) -> bool:
    if not isinstance(status_obj, dict):
        return False
    sid = status_obj.get("id")
    if isinstance(sid, int) and sid == STATUS_ID_SUCCESS:
        return True
    slug = status_obj.get("slug")
    if isinstance(slug, str) and slug.strip().lower() == STATUS_SLUG_SUCCESS:
        return True
    return False


def _extract_bank_ref(data: Any) -> str | None:
    """Pull a real bank/gateway reference out of a verify response if present.

    Basalam's TransactionPublicResource has a `methods_data` list where each
    item may include a bank reference (key names vary by gateway). We scan
    permissively and prefer non-empty strings.
    """
    if not isinstance(data, dict):
        return None
    methods = data.get("methods_data")
    if isinstance(methods, list):
        for item in methods:
            if not isinstance(item, dict):
                continue
            for key in ("ref_id", "bank_ref", "bank_reference", "reference", "trace_no", "trace_number"):
                val = item.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
                if isinstance(val, int):
                    return str(val)
    return None


def _is_already_verified(exc: PaymentBridgeError) -> bool:
    """Recognise the 'already verified' branch of a 422 from Basalam pay.

    Match conditions (any one is enough), in order of trust:
      1. Structured `status` field in the error envelope is success-shaped.
      2. Explicit Persian/English phrase in the message string.
    Bare 'already' or 'verified' substring matches are NOT enough — they
    can appear in unrelated 422s (e.g. "transaction cannot be verified
    while pending").
    """
    detail = exc.detail
    if isinstance(detail, dict) and _is_status_success(detail.get("status")):
        return True

    text = str(exc)
    if isinstance(detail, dict):
        for key in ("message", "error", "detail"):
            val = detail.get(key)
            if isinstance(val, str):
                text = f"{text} {val}"

    text_lower = text.lower()
    for phrase in ALREADY_VERIFIED_PHRASES:
        if phrase in text or phrase.lower() in text_lower:
            return True
    return False
