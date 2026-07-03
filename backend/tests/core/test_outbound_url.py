"""Tests for outbound URL safety policy."""

import socket
from types import SimpleNamespace

import pytest

from app.core import outbound_url
from app.core.outbound_url import UnsafeOutboundUrlError, assert_safe_outbound_url


def _loopback_getaddrinfo(
    *_args: object, **_kwargs: object
) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 80))]


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/health",
        "http://localhost/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "file:///etc/passwd",
        "ftp://example.com/",
    ],
)
def test_assert_safe_outbound_url_rejects_unsafe_targets(url: str) -> None:
    with pytest.raises(UnsafeOutboundUrlError):
        assert_safe_outbound_url(url)


def test_dot_localhost_is_resolved_not_bypassed(monkeypatch: pytest.MonkeyPatch) -> None:
    """`.localhost` must not skip SSRF checks; it resolves to loopback and is blocked."""
    monkeypatch.setattr(socket, "getaddrinfo", _loopback_getaddrinfo)
    with pytest.raises(UnsafeOutboundUrlError):
        assert_safe_outbound_url("http://evil.localhost/")


def test_reserved_test_tlds_bypass_resolution_in_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """.test/.example/.invalid stay a DNS-free escape hatch in local/test."""
    monkeypatch.setattr(outbound_url, "get_settings", lambda: SimpleNamespace(environment="local"))

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("getaddrinfo should not be called for reserved test TLDs")

    monkeypatch.setattr(socket, "getaddrinfo", boom)
    assert_safe_outbound_url("http://fixture.test/jobs")
    assert_safe_outbound_url("http://fixture.example/jobs")
    assert_safe_outbound_url("http://fixture.invalid/jobs")


def test_reserved_test_tlds_resolved_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Outside local/test the escape hatch is off: reserved TLDs resolve + IP-check."""
    monkeypatch.setattr(
        outbound_url, "get_settings", lambda: SimpleNamespace(environment="production")
    )
    monkeypatch.setattr(socket, "getaddrinfo", _loopback_getaddrinfo)
    with pytest.raises(UnsafeOutboundUrlError):
        assert_safe_outbound_url("http://internal-api.test/")


def test_assert_safe_outbound_url_allows_public_https() -> None:
    assert_safe_outbound_url("https://example.com/jobs")


def test_rejects_url_without_hostname() -> None:
    with pytest.raises(UnsafeOutboundUrlError, match="missing a hostname"):
        assert_safe_outbound_url("http:///path-only")


def test_rejects_unresolvable_hostname(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise socket.gaierror("no such host")

    monkeypatch.setattr(socket, "getaddrinfo", _raise)
    with pytest.raises(UnsafeOutboundUrlError, match="Unable to resolve"):
        assert_safe_outbound_url("https://does-not-exist.example.com/")


def test_rejects_hostname_with_no_addresses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [])
    with pytest.raises(UnsafeOutboundUrlError, match="Unable to resolve"):
        assert_safe_outbound_url("https://empty-dns.example.com/")
