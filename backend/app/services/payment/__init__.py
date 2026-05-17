"""Payment-gateway adapters.

Two implementations of the same `PaymentBridge` Protocol live here:

  - ShopyaarPaymentService  → pay.ejourney.ir-compatible bridge
  - BasalamPaymentService   → Basalam OpenAPI /v1/pay/* endpoints

Callers should depend on the Protocol and obtain a concrete instance via
`get_payment_bridge()`, which selects the adapter from
`settings.payment_provider` (default: "shopyaar").
"""
from __future__ import annotations

from app.core.config import Settings, get_settings
from app.services.payment.base import (
    CreatePaymentResult,
    HttpAdapterBase,
    PaymentBridge,
    PaymentBridgeError,
    VerifyPaymentResult,
    mask_secret,
)
from app.services.payment.basalam import BasalamPaymentService
from app.services.payment.shopyaar import ShopyaarPaymentService


def get_payment_bridge(settings: Settings | None = None) -> PaymentBridge:
    cfg = settings or get_settings()
    provider = (cfg.payment_provider or "shopyaar").strip().lower()
    if provider == "basalam":
        return BasalamPaymentService(cfg)
    return ShopyaarPaymentService(cfg)


__all__ = [
    "BasalamPaymentService",
    "CreatePaymentResult",
    "HttpAdapterBase",
    "PaymentBridge",
    "PaymentBridgeError",
    "ShopyaarPaymentService",
    "VerifyPaymentResult",
    "get_payment_bridge",
    "mask_secret",
]
