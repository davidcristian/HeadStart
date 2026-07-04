"""Smoke tests for the Celery app wiring and worker-process signal handlers."""

from __future__ import annotations

from unittest.mock import patch

from app.worker import celery_app as celery_module


def test_celery_app_configured() -> None:
    assert celery_module.celery_app.main == "headstart"
    # Importing the module registers the task functions on the app.
    assert "app.worker.tasks.run_search" in celery_module.celery_app.tasks
    conf = celery_module.celery_app.conf
    assert conf.task_acks_late is True
    assert conf.task_reject_on_worker_lost is True
    assert conf.task_soft_time_limit == celery_module._TASK_SOFT_TIME_LIMIT_SECONDS
    assert conf.task_time_limit == celery_module._TASK_TIME_LIMIT_SECONDS
    assert conf.result_expires == celery_module._RESULT_EXPIRES_SECONDS


def test_worker_process_init_starts_metrics_server() -> None:
    with patch.object(celery_module, "start_metrics_server") as mock_start:
        celery_module._start_worker_metrics_server()
    mock_start.assert_called_once_with(celery_module.settings.metrics_port)


def test_worker_process_shutdown_closes_browser() -> None:
    with patch("app.scrapers.playwright_browser.close_browser") as mock_close:
        celery_module._close_playwright_browser()
    mock_close.assert_called_once_with()
