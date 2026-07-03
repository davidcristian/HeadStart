"""Smoke test for the application root endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_root_returns_service_metadata(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "HeadStart API"
    assert body["health"] == "/api/v1/health"
    assert body["docs"] == "/docs"
