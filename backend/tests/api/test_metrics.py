"""Tests for the Prometheus /metrics endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app


@pytest.fixture
def metrics_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Fresh app with metrics enabled and no auth token."""
    monkeypatch.setenv("METRICS_ENABLED", "true")
    monkeypatch.setenv("METRICS_TOKEN", "")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()


def test_metrics_endpoint_exposes_prometheus_text(metrics_client: TestClient) -> None:
    resp = metrics_client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "headstart_pipeline_runs_total" in body
    assert "headstart_scrape_runs_total" in body
    assert "headstart_notification_deliveries_total" in body


def test_metrics_disabled_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        assert client.get("/metrics").status_code == 404
    get_settings.cache_clear()


def test_metrics_requires_bearer_token_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "true")
    monkeypatch.setenv("METRICS_TOKEN", "secret-metrics-token")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        assert client.get("/metrics").status_code == 401
        resp = client.get("/metrics", headers={"Authorization": "Bearer secret-metrics-token"})
        assert resp.status_code == 200
    get_settings.cache_clear()


def test_derived_metrics_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    monkeypatch.setenv("METRICS_PORT", "9191")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.metrics_enabled is False
    assert settings.metrics_port == 9191
