"""Unit tests for the Shopyaar payment adapter.

Covers: bypass mode, refusal on misconfig (no silent bypass), success
path, non-2xx error mapping, timeout mapping, header masking, and the
verify-with-authority query param.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.services.payment import (
    PaymentBridgeError,
    ShopyaarPaymentService,
    get_payment_bridge,
)
from app.services.payment.base import mask_secret


def _make_settings(**overrides: Any) -> Settings:
    base = dict(
        database_url="sqlite+aiosqlite:///./test_payment.db",
        session_secret="x" * 32,
        fernet_key="0" * 44 + "=",
        app_origin="http://localhost:3000",
        payment_provider="shopyaar",
        payment_bridge_url="https://pay.example.test",
        payment_bridge_api_key="secret-test-key-1234567890",
        payment_bridge_callback_url="https://shop.example.test/cb",
        payment_bridge_enabled=True,
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


def test_mask_secret_hides_tail():
    assert mask_secret(None) is None
    assert mask_secret("") == ""
    assert mask_secret("short") == "sho..."
    assert mask_secret("supersecret-token-12345") == "supersecre..."


def test_factory_unknown_provider_raises():
    cfg = _make_settings(payment_provider="zarinpal")
    with pytest.raises(ValueError) as ei:
        get_payment_bridge(cfg)
    assert "zarinpal" in str(ei.value)


def test_factory_picks_shopyaar_by_default():
    cfg = _make_settings(payment_provider="")
    bridge = get_payment_bridge(cfg)
    assert isinstance(bridge, ShopyaarPaymentService)


async def test_bypass_create_payment_returns_mock_without_network():
    p = ShopyaarPaymentService(_make_settings(payment_bridge_bypass=True))
    out = await p.create_payment(amount=10000, callback_url="https://cb")
    assert out.bypass is True
    assert out.token.startswith("mock-")
    assert out.url == "https://cb"


async def test_bypass_verify_returns_mock():
    p = ShopyaarPaymentService(_make_settings(payment_bridge_bypass=True))
    out = await p.verify_payment(token="abc")
    assert out.success is True
    assert out.bypass is True
    assert out.ref_id is not None and out.ref_id.startswith("mock-ref-")


async def test_unconfigured_without_bypass_flag_refuses():
    # No URL, no explicit bypass flag → must NOT silently mock-credit.
    p = ShopyaarPaymentService(_make_settings(
        payment_bridge_url="",
        payment_bridge_enabled=False,
        payment_bridge_bypass=False,
    ))
    assert p.bypass is False
    with pytest.raises(PaymentBridgeError) as ei:
        await p.create_payment(amount=10)
    assert "not configured" in str(ei.value).lower()


async def test_create_payment_success_calls_bridge_with_headers_and_body(monkeypatch):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode("utf-8")
        return httpx.Response(
            200,
            json={"status": True, "token": "tok-1", "url": "https://gw/pay/tok-1"},
        )

    _patch_transport(monkeypatch, handler)

    p = ShopyaarPaymentService(_make_settings())
    out = await p.create_payment(amount=10000, callback_url="https://cb", user_phone="09120000000")

    assert out.token == "tok-1"
    assert out.url == "https://gw/pay/tok-1"
    assert captured["url"] == "https://pay.example.test/payments/create"
    assert captured["method"] == "POST"
    assert captured["headers"]["content-type"] == "application/json"
    assert captured["headers"]["x-api-key"] == "secret-test-key-1234567890"
    sent_body = json.loads(captured["body"])
    assert sent_body == {
        "amount": 10000,
        "callback_url": "https://cb",
        "user_phone": "09120000000",
    }


async def test_verify_payment_appends_authority_query_param(monkeypatch):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"status": True, "ref_id": "ref-1"})

    _patch_transport(monkeypatch, handler)

    p = ShopyaarPaymentService(_make_settings())
    out = await p.verify_payment(token="abc123")

    assert out.success is True
    assert out.ref_id == "ref-1"
    assert captured["url"] == "https://pay.example.test/payments/verify?authority=abc123"


async def test_non_2xx_response_raises_payment_bridge_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"message": "amount must be positive"})

    _patch_transport(monkeypatch, handler)

    p = ShopyaarPaymentService(_make_settings())
    with pytest.raises(PaymentBridgeError) as ei:
        await p.create_payment(amount=-5)
    assert "amount must be positive" in str(ei.value)
    assert ei.value.status_code == 400


async def test_timeout_raises_friendly_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("simulated timeout", request=request)

    _patch_transport(monkeypatch, handler)

    p = ShopyaarPaymentService(_make_settings())
    with pytest.raises(PaymentBridgeError) as ei:
        await p.create_payment(amount=1)
    assert "timeout" in str(ei.value).lower()
