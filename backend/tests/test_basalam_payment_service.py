"""Unit tests for the Basalam OpenAPI pay adapter.

Covers: refusal on misconfig, bypass mode, create_payment request shape
and response mapping, verify success on `status.id == 3` / `slug ==
"success"`, the narrow 422 "already verified" idempotency branch, the
real-422 path (which must raise), URL-encoding of `hash_id`, and
`ref_id` extraction from `methods_data`.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.services.payment import (
    BasalamPaymentService,
    PaymentBridgeError,
    get_payment_bridge,
)


def _make_settings(**overrides: Any) -> Settings:
    base = dict(
        database_url="sqlite+aiosqlite:///./test_basalam_pay.db",
        session_secret="x" * 32,
        fernet_key="0" * 44 + "=",
        app_origin="http://localhost:3000",
        payment_provider="basalam",
        basalam_openapi_base="https://openapi.basalam.test",
        basalam_pay_gateway_secret="gw-secret-abcdef-1234567890",
        payment_bridge_callback_url="https://shop.example.test/wallet/cb",
        payment_bridge_bypass=False,
    )
    base.update(overrides)
    return Settings(**base)


def _patch_transport(monkeypatch, handler) -> None:
    transport = httpx.MockTransport(handler)

    class PatchedClient(httpx.AsyncClient):
        def __init__(self, *a: Any, **kw: Any) -> None:
            kw["transport"] = transport
            super().__init__(*a, **kw)

    monkeypatch.setattr("app.services.payment.base.httpx.AsyncClient", PatchedClient)


def test_factory_picks_basalam():
    bridge = get_payment_bridge(_make_settings())
    assert isinstance(bridge, BasalamPaymentService)


async def test_missing_gateway_secret_refuses_without_bypass_flag():
    p = BasalamPaymentService(_make_settings(basalam_pay_gateway_secret=""))
    assert p.bypass is False
    with pytest.raises(PaymentBridgeError) as ei:
        await p.create_payment(amount=50_000)
    assert "not configured" in str(ei.value).lower()


async def test_bypass_flag_enables_mock_even_without_secret():
    p = BasalamPaymentService(_make_settings(
        basalam_pay_gateway_secret="",
        payment_bridge_bypass=True,
    ))
    out = await p.create_payment(amount=50_000, callback_url="https://cb")
    assert out.bypass is True
    assert out.token.startswith("mock-")
    verify = await p.verify_payment(token=out.token)
    assert verify.bypass is True
    assert verify.success is True


async def test_create_payment_sends_required_fields_and_secret_header(monkeypatch):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "hash_id": "tx_hash_xyz",
                "pay_url": "https://openapi.basalam.test/pay/tx_hash_xyz",
                "order": {"amount": 50000, "fee": 0, "total_amount": 50000},
                "expired_at": "2026-05-18T01:00:00Z",
                "gateway": {"title": "Basalam Pay"},
                "pay_methods": [],
            },
        )

    _patch_transport(monkeypatch, handler)

    p = BasalamPaymentService(_make_settings())
    out = await p.create_payment(
        amount=50_000, callback_url="https://shop/cb", description="topup",
    )

    assert out.token == "tx_hash_xyz"
    assert out.url == "https://openapi.basalam.test/pay/tx_hash_xyz"
    assert out.reference_id is not None and len(out.reference_id) >= 16
    assert captured["url"] == "https://openapi.basalam.test/v1/pay/pre-transactions"
    assert captured["method"] == "POST"
    assert captured["headers"]["x-gateway-secret"] == "gw-secret-abcdef-1234567890"
    assert captured["body"]["amount"] == 50_000
    assert captured["body"]["callback_url"] == "https://shop/cb"
    assert captured["body"]["description"] == "topup"
    assert captured["body"]["reference_id"] == out.reference_id


async def test_create_payment_response_missing_hash_id_raises(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"pay_url": "https://x"})

    _patch_transport(monkeypatch, handler)
    p = BasalamPaymentService(_make_settings())
    with pytest.raises(PaymentBridgeError) as ei:
        await p.create_payment(amount=50_000)
    assert "missing" in str(ei.value).lower()


async def test_verify_success_status_id_3(monkeypatch):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "hash_id": "tx_hash_xyz",
                "reference_id": "my-ref",
                "status": {"id": 3, "slug": "success", "title": "موفق"},
                "methods_data": [
                    {"ref_id": "RB-998877", "amount": 50000},
                ],
            },
        )

    _patch_transport(monkeypatch, handler)
    p = BasalamPaymentService(_make_settings())
    out = await p.verify_payment(token="tx_hash_xyz")

    assert out.success is True
    assert out.ref_id == "RB-998877"  # extracted from methods_data, not hash_id
    assert captured["url"] == "https://openapi.basalam.test/v1/pay/transactions/tx_hash_xyz/verify"


async def test_verify_success_via_slug_when_no_id(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "hash_id": "tx_hash_xyz",
                "status": {"slug": "success", "title": "موفق"},
            },
        )

    _patch_transport(monkeypatch, handler)
    p = BasalamPaymentService(_make_settings())
    out = await p.verify_payment(token="tx_hash_xyz")
    assert out.success is True
    assert out.ref_id == "tx_hash_xyz"  # fallback when no methods_data ref


async def test_verify_failure_when_status_not_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "hash_id": "tx_hash_xyz",
                "status": {"id": 4, "slug": "failed", "title": "ناموفق"},
            },
        )

    _patch_transport(monkeypatch, handler)
    p = BasalamPaymentService(_make_settings())
    out = await p.verify_payment(token="tx_hash_xyz")
    assert out.success is False


async def test_verify_422_already_verified_via_phrase_is_idempotent(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={"message": "این تراکنش تایید قبلی شده است."},
        )

    _patch_transport(monkeypatch, handler)
    p = BasalamPaymentService(_make_settings())
    out = await p.verify_payment(token="tx_hash_xyz")
    assert out.success is True
    assert out.ref_id == "tx_hash_xyz"


async def test_verify_422_already_verified_via_structured_status_is_idempotent(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "message": "transaction already verified",
                "status": {"id": 3, "slug": "success"},
            },
        )

    _patch_transport(monkeypatch, handler)
    p = BasalamPaymentService(_make_settings())
    out = await p.verify_payment(token="tx_hash_xyz")
    assert out.success is True


async def test_verify_422_real_validation_error_raises(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "detail": [
                    {"loc": ["path", "hash_id"], "msg": "value is not a valid hash"},
                ],
            },
        )

    _patch_transport(monkeypatch, handler)
    p = BasalamPaymentService(_make_settings())
    with pytest.raises(PaymentBridgeError) as ei:
        await p.verify_payment(token="not-a-real-hash")
    assert ei.value.status_code == 422
    assert "not a valid hash" in str(ei.value)


async def test_verify_url_encodes_token_with_special_chars(monkeypatch):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={"hash_id": "raw", "status": {"id": 3, "slug": "success"}},
        )

    _patch_transport(monkeypatch, handler)
    p = BasalamPaymentService(_make_settings())
    await p.verify_payment(token="weird/token?with=stuff")
    assert "weird%2Ftoken%3Fwith%3Dstuff" in captured["url"]


async def test_verify_timeout_raises(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated", request=request)

    _patch_transport(monkeypatch, handler)
    p = BasalamPaymentService(_make_settings())
    with pytest.raises(PaymentBridgeError) as ei:
        await p.verify_payment(token="tx")
    assert "timeout" in str(ei.value).lower()
