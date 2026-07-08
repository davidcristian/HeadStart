"""Tests for HTTP request metadata extraction used in GDPR audit logging."""

import pytest
from starlette.requests import Request

from app.core import request_meta as request_meta_mod
from app.core.request_meta import request_meta


def _make_request(
    *,
    headers: list[tuple[bytes, bytes]] | None = None,
    client_host: str | None = "203.0.113.10",
) -> Request:
    scope: dict = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers or [],
    }
    if client_host is not None:
        scope["client"] = (client_host, 12345)
    return Request(scope)


def test_request_meta_ignores_xff_without_trusted_proxies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AUT-17: forged XFF must not win when TRUSTED_PROXY_CIDRS is empty."""
    monkeypatch.setattr(request_meta_mod.settings, "trusted_proxy_cidrs", [])
    request = _make_request(
        headers=[
            (b"x-forwarded-for", b"198.51.100.2, 10.0.0.1"),
            (b"user-agent", b"pytest-agent/2.0"),
        ],
        client_host="203.0.113.10",
    )
    meta = request_meta(request)
    assert meta.ip_address == "203.0.113.10"
    assert meta.user_agent == "pytest-agent/2.0"


def test_request_meta_uses_xff_when_peer_is_trusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trusted peer: walk XFF right→left past trusted hops to the client."""
    monkeypatch.setattr(
        request_meta_mod.settings,
        "trusted_proxy_cidrs",
        ["10.0.0.0/8"],
    )
    request = _make_request(
        headers=[(b"x-forwarded-for", b"198.51.100.2, 10.0.0.1")],
        client_host="10.0.0.5",
    )
    meta = request_meta(request)
    assert meta.ip_address == "198.51.100.2"


def test_request_meta_skips_trusted_xff_hops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multi-proxy chain: skip every trusted hop until the external client."""
    monkeypatch.setattr(
        request_meta_mod.settings,
        "trusted_proxy_cidrs",
        ["10.0.0.0/8", "192.168.0.0/16"],
    )
    request = _make_request(
        headers=[(b"x-forwarded-for", b"203.0.113.9, 10.1.2.3, 192.168.1.1")],
        client_host="10.0.0.9",
    )
    assert request_meta(request).ip_address == "203.0.113.9"


def test_request_meta_falls_back_when_xff_all_trusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If every XFF hop is trusted, keep the TCP peer."""
    monkeypatch.setattr(
        request_meta_mod.settings,
        "trusted_proxy_cidrs",
        ["10.0.0.0/8"],
    )
    request = _make_request(
        headers=[(b"x-forwarded-for", b"10.0.0.2, 10.0.0.3")],
        client_host="10.0.0.1",
    )
    assert request_meta(request).ip_address == "10.0.0.1"


def test_request_meta_ignores_xff_from_untrusted_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct clients cannot spoof XFF even when proxies are configured."""
    monkeypatch.setattr(
        request_meta_mod.settings,
        "trusted_proxy_cidrs",
        ["10.0.0.0/8"],
    )
    request = _make_request(
        headers=[(b"x-forwarded-for", b"198.51.100.2")],
        client_host="203.0.113.10",
    )
    assert request_meta(request).ip_address == "203.0.113.10"


def test_request_meta_rejects_overlong_and_invalid_ips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Overlong / non-IP tokens must not reach String(45) persistence (AUT-17)."""
    monkeypatch.setattr(
        request_meta_mod.settings,
        "trusted_proxy_cidrs",
        ["10.0.0.0/8"],
    )
    # Rightmost hop invalid → continue; then accept the real client.
    request = _make_request(
        headers=[(b"x-forwarded-for", b"198.51.100.7, not-an-ip")],
        client_host="10.0.0.1",
    )
    assert request_meta(request).ip_address == "198.51.100.7"

    overlong = "1" * 46
    assert request_meta(_make_request(client_host=overlong)).ip_address is None
    assert request_meta(_make_request(client_host="   ")).ip_address is None


def test_request_meta_normalizes_ipv6(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        request_meta_mod.settings,
        "trusted_proxy_cidrs",
        ["fd00::/8"],
    )
    request = _make_request(
        headers=[(b"x-forwarded-for", b"[2001:db8::1]")],
        client_host="fd00::1",
    )
    assert request_meta(request).ip_address == "2001:db8::1"


def test_request_meta_trusted_peer_without_xff_keeps_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        request_meta_mod.settings,
        "trusted_proxy_cidrs",
        ["10.0.0.0/8"],
    )
    request = _make_request(client_host="10.0.0.5")
    assert request_meta(request).ip_address == "10.0.0.5"


def test_request_meta_falls_back_to_client_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(request_meta_mod.settings, "trusted_proxy_cidrs", [])
    request = _make_request(client_host="203.0.113.55")
    meta = request_meta(request)
    assert meta.ip_address == "203.0.113.55"
    assert meta.user_agent is None


def test_request_meta_handles_missing_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(request_meta_mod.settings, "trusted_proxy_cidrs", [])
    request = _make_request(client_host=None)
    meta = request_meta(request)
    assert meta.ip_address is None
    assert meta.user_agent is None


def test_request_meta_drops_non_ip_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Starlette TestClient uses host 'testclient' — not a storable IP."""
    monkeypatch.setattr(request_meta_mod.settings, "trusted_proxy_cidrs", [])
    request = _make_request(client_host="testclient")
    assert request_meta(request).ip_address is None
