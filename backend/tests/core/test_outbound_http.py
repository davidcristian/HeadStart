"""Tests for pinned outbound HTTP helpers."""

from __future__ import annotations

import httpx
import pytest

from app.core.outbound_http import apply_outbound_pin, pinned_request


def test_pinned_request_uses_resolved_ip_and_preserves_host_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pinned connects must not re-resolve DNS at request time (rebinding guard)."""
    monkeypatch.setattr(
        "app.core.outbound_http.pin_outbound_request",
        lambda url: type(
            "Pinned",
            (),
            {"request_url": "http://93.184.216.34/notify", "host_header": "hooks.example.com"},
        )(),
    )
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    response = pinned_request(client, "POST", "https://hooks.example.com/notify", json={"ok": True})

    assert response.status_code == 200
    assert len(captured) == 1
    assert str(captured[0].url) == "http://93.184.216.34/notify"
    assert captured[0].headers["Host"] == "hooks.example.com"


def test_apply_outbound_pin_sets_host_even_when_url_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Host header must be set even when the resolved IP matches the original URL."""
    original = "https://example.com/path"
    monkeypatch.setattr(
        "app.core.outbound_http.pin_outbound_request",
        lambda url: type(
            "Pinned",
            (),
            {"request_url": url, "host_header": "example.com"},
        )(),
    )
    request = httpx.Request("GET", original)
    apply_outbound_pin(request)
    assert str(request.url) == original
    assert request.headers["Host"] == "example.com"
