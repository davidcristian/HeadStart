"""Tests for API security response headers (AUT-23)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.responses import Response

from app.core.security_headers import (
    CSP_FRAME_ANCESTORS,
    HSTS_VALUE,
    REFERRER_POLICY,
    X_CONTENT_TYPE_OPTIONS,
    X_FRAME_OPTIONS,
    apply_security_headers,
)
from app.main import create_app


def test_apply_security_headers_sets_baseline_without_hsts() -> None:
    response = Response(content=b"ok")
    apply_security_headers(response, include_hsts=False)
    assert response.headers["X-Content-Type-Options"] == X_CONTENT_TYPE_OPTIONS
    assert response.headers["X-Frame-Options"] == X_FRAME_OPTIONS
    assert response.headers["Referrer-Policy"] == REFERRER_POLICY
    assert response.headers["Content-Security-Policy"] == CSP_FRAME_ANCESTORS
    assert "Strict-Transport-Security" not in response.headers


def test_apply_security_headers_adds_hsts_when_requested() -> None:
    response = Response(content=b"ok")
    apply_security_headers(response, include_hsts=True)
    assert response.headers["Strict-Transport-Security"] == HSTS_VALUE


def test_apply_security_headers_does_not_overwrite_existing() -> None:
    response = Response(content=b"ok")
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    apply_security_headers(response, include_hsts=True)
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Strict-Transport-Security"] == HSTS_VALUE


def test_health_response_includes_security_headers(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == X_CONTENT_TYPE_OPTIONS
    assert response.headers["X-Frame-Options"] == X_FRAME_OPTIONS
    assert response.headers["Referrer-Policy"] == REFERRER_POLICY
    assert response.headers["Content-Security-Policy"] == CSP_FRAME_ANCESTORS
    # Default test ENVIRONMENT is local/test — no HSTS pin for localhost HTTP.
    assert "Strict-Transport-Security" not in response.headers


def test_middleware_adds_hsts_outside_local() -> None:
    fake = SimpleNamespace(environment="production")
    with (
        patch("app.core.security_headers.get_settings", return_value=fake),
        TestClient(create_app()) as client,
    ):
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["Strict-Transport-Security"] == HSTS_VALUE
    assert response.headers["X-Content-Type-Options"] == X_CONTENT_TYPE_OPTIONS


def test_middleware_skips_hsts_in_local_environment() -> None:
    fake = SimpleNamespace(environment="local")
    with (
        patch("app.core.security_headers.get_settings", return_value=fake),
        TestClient(create_app()) as client,
    ):
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert "Strict-Transport-Security" not in response.headers
