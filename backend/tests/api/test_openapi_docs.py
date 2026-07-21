"""OpenAPI interactive docs are local/test only."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app


def test_docs_available_in_local_environment(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_docs_disabled_outside_local_environment() -> None:
    fake = SimpleNamespace(
        environment="production",
        cors_origins=["http://localhost:5173"],
        metrics_enabled=False,
        metrics_token="",
    )
    with (
        patch("app.main.get_settings", return_value=fake),
        patch("app.core.security_headers.get_settings", return_value=fake),
        TestClient(create_app()) as client,
    ):
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        root = client.get("/").json()
        assert "docs" not in root
        assert root["health"] == "/api/v1/health"
