"""Unit tests for auth rate limiting (AUT-03)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.core.exceptions import RateLimitError
from app.core.rate_limit import (
    FORGOT_EMAIL,
    LOGIN_IP,
    RateLimitRule,
    SlidingWindowRateLimiter,
    enforce_rate_limit,
    get_rate_limiter,
    limit_forgot_password,
    limit_login,
    limit_refresh,
    limit_register,
    limit_resend_verification,
    limit_token_guess,
    limit_verification_email_issue,
    reset_rate_limiter,
)


def _request(host: str = "9.9.9.9") -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [],
        "client": (host, 12345),
        "server": ("test", 80),
    }
    return Request(scope)


def test_sliding_window_allows_up_to_limit() -> None:
    limiter = SlidingWindowRateLimiter()
    rule = RateLimitRule(3, 60)
    for _ in range(3):
        limiter.hit("k", rule)
    with pytest.raises(RateLimitError, match="Too many requests"):
        limiter.hit("k", rule)


def test_sliding_window_expires_old_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = SlidingWindowRateLimiter()
    rule = RateLimitRule(1, 10)
    times = iter([100.0, 100.5, 111.0])
    monkeypatch.setattr("app.core.rate_limit.monotonic", lambda: next(times))
    limiter.hit("k", rule)
    with pytest.raises(RateLimitError):
        limiter.hit("k", rule)
    limiter.hit("k", rule)  # prior hit aged out of the window


def test_reset_clears_counters() -> None:
    reset_rate_limiter()
    rule = RateLimitRule(1, 60)
    enforce_rate_limit("once", rule)
    with pytest.raises(RateLimitError):
        enforce_rate_limit("once", rule)
    reset_rate_limiter()
    enforce_rate_limit("once", rule)
    assert get_rate_limiter() is get_rate_limiter()


def test_limit_helpers_key_by_ip_and_email() -> None:
    reset_rate_limiter()
    req = _request()

    for i in range(LOGIN_IP.limit):
        limit_login(req, f"user{i}@example.com")
    with pytest.raises(RateLimitError):
        limit_login(req, "overflow@example.com")  # same IP bucket exhausted

    reset_rate_limiter()
    for _ in range(FORGOT_EMAIL.limit):
        limit_forgot_password(req, "victim@example.com")
    with pytest.raises(RateLimitError):
        limit_forgot_password(req, "victim@example.com")

    reset_rate_limiter()
    limit_register(req)
    limit_token_guess(req, kind="reset")
    limit_token_guess(req, kind="verify")
    limit_refresh(req)
    limit_resend_verification(42)
    limit_verification_email_issue("new@example.com")


def test_unknown_client_falls_back_to_unknown_subject() -> None:
    reset_rate_limiter()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [],
        "client": None,
        "server": ("test", 80),
    }
    req = Request(scope)
    limit_refresh(req)


def test_login_returns_429_when_email_limit_exceeded(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "rate@example.com", "password": "password123"},
    )
    for _ in range(10):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "rate@example.com", "password": "wrong-password"},
        )
        assert resp.status_code == 400
    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "rate@example.com", "password": "wrong-password"},
    )
    assert blocked.status_code == 429
    assert "Too many requests" in blocked.json()["detail"]


def test_forgot_password_returns_429_after_email_cap(client: TestClient) -> None:
    with patch("app.services.auth_password.send_password_reset_email"):
        for _ in range(5):
            resp = client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "bomb@example.com"},
            )
            assert resp.status_code == 200
        blocked = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "bomb@example.com"},
        )
    assert blocked.status_code == 429


def test_register_returns_429_when_ip_cap_exceeded(client: TestClient) -> None:
    with patch("app.services.auth.send_verification_email"):
        for i in range(10):
            resp = client.post(
                "/api/v1/auth/register",
                json={"email": f"u{i}@example.com", "password": "password123"},
            )
            assert resp.status_code == 201, resp.text
        blocked = client.post(
            "/api/v1/auth/register",
            json={"email": "overflow@example.com", "password": "password123"},
        )
    assert blocked.status_code == 429
