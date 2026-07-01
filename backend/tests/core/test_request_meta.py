"""Tests for HTTP request metadata extraction used in GDPR audit logging."""

from starlette.requests import Request

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


def test_request_meta_uses_first_x_forwarded_for_ip() -> None:
    request = _make_request(
        headers=[
            (b"x-forwarded-for", b"198.51.100.2, 10.0.0.1"),
            (b"user-agent", b"pytest-agent/2.0"),
        ],
        client_host="203.0.113.10",
    )
    meta = request_meta(request)
    assert meta.ip_address == "198.51.100.2"
    assert meta.user_agent == "pytest-agent/2.0"


def test_request_meta_falls_back_to_client_host() -> None:
    request = _make_request(client_host="203.0.113.55")
    meta = request_meta(request)
    assert meta.ip_address == "203.0.113.55"
    assert meta.user_agent is None


def test_request_meta_handles_missing_client() -> None:
    request = _make_request(client_host=None)
    meta = request_meta(request)
    assert meta.ip_address is None
    assert meta.user_agent is None
