"""Tests for the metrics recording helpers (enabled + disabled paths)."""

from __future__ import annotations

import errno
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core import metrics


@pytest.fixture
def metrics_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        metrics,
        "get_settings",
        lambda: SimpleNamespace(metrics_enabled=True, metrics_token=""),
    )


@pytest.fixture
def metrics_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        metrics,
        "get_settings",
        lambda: SimpleNamespace(metrics_enabled=False, metrics_token=""),
    )


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


def test_metrics_bearer_authorized_when_token_unset() -> None:
    assert metrics.metrics_bearer_authorized("", "") is True
    assert metrics.metrics_bearer_authorized("Bearer anything", "") is True


def test_metrics_bearer_authorized_requires_exact_bearer() -> None:
    assert metrics.metrics_bearer_authorized("Bearer secret", "secret") is True
    assert metrics.metrics_bearer_authorized("Bearer wrong", "secret") is False
    assert metrics.metrics_bearer_authorized("", "secret") is False
    assert metrics.metrics_bearer_authorized("secret", "secret") is False


def test_authorized_metrics_app_rejects_missing_bearer() -> None:
    app = metrics.authorized_metrics_app("worker-token")
    status: list[str] = []

    def start_response(status_line: str, _headers: list[tuple[str, str]]) -> None:
        status.append(status_line)

    body = b"".join(app({"HTTP_AUTHORIZATION": ""}, start_response))
    assert status == ["401 Unauthorized"]
    assert b"Unauthorized" in body


def test_authorized_metrics_app_allows_valid_bearer() -> None:
    app = metrics.authorized_metrics_app("worker-token")
    status: list[str] = []

    def start_response(status_line: str, _headers: list[tuple[str, str]]) -> None:
        status.append(status_line)

    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/metrics",
        "HTTP_AUTHORIZATION": "Bearer worker-token",
    }
    body = b"".join(app(environ, start_response))
    assert status[0].startswith("200")
    assert b"headstart_" in body or b"#" in body


def test_authorized_metrics_app_open_when_token_empty() -> None:
    app = metrics.authorized_metrics_app("")
    status: list[str] = []

    def start_response(status_line: str, _headers: list[tuple[str, str]]) -> None:
        status.append(status_line)

    body = b"".join(app({"REQUEST_METHOD": "GET", "PATH_INFO": "/metrics"}, start_response))
    assert status[0].startswith("200")
    assert body


def test_start_metrics_server_noop_when_disabled(metrics_disabled: None) -> None:
    with patch.object(metrics, "make_server") as mock_make:
        metrics.start_metrics_server(9000)
    mock_make.assert_not_called()


def test_start_metrics_server_starts_when_enabled(metrics_enabled: None) -> None:
    httpd = MagicMock()
    with (
        patch.object(metrics, "make_server", return_value=httpd) as mock_make,
        patch.object(metrics.threading, "Thread") as mock_thread,
    ):
        metrics.start_metrics_server(9001)
    mock_make.assert_called_once()
    assert mock_make.call_args.args[0] == "0.0.0.0"
    assert mock_make.call_args.args[1] == 9001
    mock_thread.assert_called_once()
    mock_thread.return_value.start.assert_called_once()


def test_start_metrics_server_skips_when_port_in_use(metrics_enabled: None) -> None:
    """Prefork siblings must not crash when METRICS_PORT is already bound (XCT-13)."""
    with patch.object(
        metrics,
        "make_server",
        side_effect=OSError(errno.EADDRINUSE, "Address already in use"),
    ):
        metrics.start_metrics_server(9090)


def test_start_metrics_server_reraises_other_oserror(metrics_enabled: None) -> None:
    with (
        patch.object(
            metrics,
            "make_server",
            side_effect=OSError(errno.EACCES, "Permission denied"),
        ),
        pytest.raises(OSError) as exc_info,
    ):
        metrics.start_metrics_server(9090)
    assert exc_info.value.errno == errno.EACCES


def test_silent_handler_swallows_access_log() -> None:
    handler = metrics._SilentHandler.__new__(metrics._SilentHandler)
    handler.log_message("%s", "ignored")
