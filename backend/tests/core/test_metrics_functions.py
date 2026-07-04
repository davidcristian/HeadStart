"""Tests for the metrics recording helpers (enabled + disabled paths)."""

from __future__ import annotations

import errno
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core import metrics


@pytest.fixture
def metrics_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metrics, "get_settings", lambda: SimpleNamespace(metrics_enabled=True))


@pytest.fixture
def metrics_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metrics, "get_settings", lambda: SimpleNamespace(metrics_enabled=False))


def test_record_helpers_noop_when_disabled(metrics_disabled: None) -> None:
    # None of these should touch a collector when metrics are off.
    metrics.record_pipeline_run("success")
    metrics.record_scrape("greenhouse", "success", 0.1, 5)
    metrics.record_notification("ntfy", "sent", "immediate")
    metrics.record_digest_flush("success")
    metrics.record_scheduler_enqueued(3)
    metrics.record_auth_login_failure()


def test_record_helpers_increment_when_enabled(metrics_enabled: None) -> None:
    metrics.record_pipeline_run("success")
    metrics.record_scrape("greenhouse", "success", 0.25, 10)
    metrics.record_notification("ntfy", "sent", "digest")
    metrics.record_digest_flush("error")
    metrics.record_digest_flush("skipped_plan")
    metrics.record_scheduler_enqueued(2)
    metrics.record_auth_login_failure()

    body, content_type = metrics.render_metrics()
    assert b"headstart_pipeline_runs_total" in body
    assert b"headstart_auth_login_failures_total" in body
    assert "text" in content_type


def test_record_scheduler_enqueued_ignores_non_positive(metrics_enabled: None) -> None:
    before = metrics.SCHEDULER_SEARCHES_ENQUEUED._value.get()  # type: ignore[attr-defined]
    metrics.record_scheduler_enqueued(0)
    after = metrics.SCHEDULER_SEARCHES_ENQUEUED._value.get()  # type: ignore[attr-defined]
    assert after == before


def test_start_metrics_server_noop_when_disabled(metrics_disabled: None) -> None:
    with patch("prometheus_client.start_http_server") as mock_start:
        metrics.start_metrics_server(9000)
    mock_start.assert_not_called()


def test_start_metrics_server_starts_when_enabled(metrics_enabled: None) -> None:
    mock_start = MagicMock()
    with patch.dict(
        "sys.modules",
        {"prometheus_client": SimpleNamespace(start_http_server=mock_start)},
    ):
        metrics.start_metrics_server(9001)
    mock_start.assert_called_once_with(9001)


def test_start_metrics_server_skips_when_port_in_use(metrics_enabled: None) -> None:
    """Prefork siblings must not crash when METRICS_PORT is already bound (XCT-13)."""
    mock_start = MagicMock(side_effect=OSError(errno.EADDRINUSE, "Address already in use"))
    with patch.dict(
        "sys.modules",
        {"prometheus_client": SimpleNamespace(start_http_server=mock_start)},
    ):
        metrics.start_metrics_server(9090)
    mock_start.assert_called_once_with(9090)


def test_start_metrics_server_reraises_other_oserror(metrics_enabled: None) -> None:
    mock_start = MagicMock(side_effect=OSError(errno.EACCES, "Permission denied"))
    with (
        patch.dict(
            "sys.modules",
            {"prometheus_client": SimpleNamespace(start_http_server=mock_start)},
        ),
        pytest.raises(OSError) as exc_info,
    ):
        metrics.start_metrics_server(9090)
    assert exc_info.value.errno == errno.EACCES
