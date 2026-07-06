"""Prometheus metrics for scrape, notification, and scheduler observability."""

from __future__ import annotations

import errno
import hmac
import logging
import threading
from collections.abc import Callable, Iterable
from typing import Literal
from wsgiref.simple_server import WSGIRequestHandler, make_server
from wsgiref.types import StartResponse, WSGIEnvironment

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.core.config import get_settings

logger = logging.getLogger(__name__)

PipelineStatus = Literal["success", "error", "not_found"]
ScrapeStatus = Literal["success", "error"]
DeliveryStatus = Literal["sent", "failed"]
NotificationMode = Literal["immediate", "digest"]

PIPELINE_RUNS = Counter(
    "headstart_pipeline_runs_total",
    "Pipeline runs completed",
    ["status"],
)
SCRAPE_RUNS = Counter(
    "headstart_scrape_runs_total",
    "Scrape attempts",
    ["adapter", "status"],
)
SCRAPE_DURATION_SECONDS = Histogram(
    "headstart_scrape_duration_seconds",
    "Time spent in scraper.fetch",
    ["adapter"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)
SCRAPE_JOBS_FOUND = Histogram(
    "headstart_scrape_jobs_found",
    "Job postings returned by a scrape",
    ["adapter"],
    buckets=(0, 1, 5, 10, 25, 50, 100, 250, 500, 1000),
)
NOTIFICATION_DELIVERIES = Counter(
    "headstart_notification_deliveries_total",
    "Notification delivery attempts",
    ["notifier", "status", "mode"],
)
DIGEST_FLUSHES = Counter(
    "headstart_digest_flushes_total",
    "Digest batch flushes",
    ["status"],
)
SCHEDULER_SEARCHES_ENQUEUED = Counter(
    "headstart_scheduler_searches_enqueued_total",
    "Due searches enqueued by the scheduler",
)
AUTH_LOGIN_FAILURES = Counter(
    "headstart_auth_login_failures_total",
    "Failed login attempts (invalid credentials or inactive account)",
)

WSGIApp = Callable[[WSGIEnvironment, StartResponse], Iterable[bytes]]


def record_pipeline_run(status: PipelineStatus) -> None:
    """Record a completed pipeline run."""
    if not get_settings().metrics_enabled:
        return
    PIPELINE_RUNS.labels(status=status).inc()


def record_scrape(adapter: str, status: ScrapeStatus, duration_seconds: float, found: int) -> None:
    """Record scrape outcome, latency, and result size."""
    if not get_settings().metrics_enabled:
        return
    SCRAPE_RUNS.labels(adapter=adapter, status=status).inc()
    SCRAPE_DURATION_SECONDS.labels(adapter=adapter).observe(duration_seconds)
    SCRAPE_JOBS_FOUND.labels(adapter=adapter).observe(found)


def record_notification(notifier: str, status: DeliveryStatus, mode: NotificationMode) -> None:
    """Record one notification delivery attempt."""
    if not get_settings().metrics_enabled:
        return
    NOTIFICATION_DELIVERIES.labels(notifier=notifier, status=status, mode=mode).inc()


def record_digest_flush(status: Literal["success", "error", "skipped_plan"]) -> None:
    """Record a digest batch flush."""
    if not get_settings().metrics_enabled:
        return
    DIGEST_FLUSHES.labels(status=status).inc()


def record_scheduler_enqueued(count: int) -> None:
    """Record how many due searches were enqueued on a beat tick."""
    if not get_settings().metrics_enabled or count <= 0:
        return
    SCHEDULER_SEARCHES_ENQUEUED.inc(count)


def record_auth_login_failure() -> None:
    """Record one failed login for credential-stuffing alerts (AUT-10)."""
    if not get_settings().metrics_enabled:
        return
    AUTH_LOGIN_FAILURES.inc()


def render_metrics() -> tuple[bytes, str]:
    """Return Prometheus exposition payload and content type."""
    return generate_latest(), CONTENT_TYPE_LATEST


def metrics_bearer_authorized(authorization: str, token: str) -> bool:
    """Return True when token is unset or Authorization matches Bearer token."""
    if not token:
        return True
    expected = f"Bearer {token}".encode()
    return hmac.compare_digest(authorization.encode(), expected)


def authorized_metrics_app(token: str) -> WSGIApp:
    """WSGI app that exposes Prometheus metrics behind optional Bearer auth (AUT-06)."""
    from prometheus_client import make_wsgi_app

    base_app = make_wsgi_app()

    def app(environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
        auth = environ.get("HTTP_AUTHORIZATION", "")
        if not metrics_bearer_authorized(auth, token):
            start_response("401 Unauthorized", [("Content-Type", "text/plain")])
            return [b"Unauthorized\n"]
        return base_app(environ, start_response)

    return app


class _SilentHandler(WSGIRequestHandler):
    """Suppress per-request access logs from the worker metrics server."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def start_metrics_server(port: int) -> None:
    """Expose /metrics on a background HTTP server (worker processes).

    Prefork Celery children all call this on the same ``METRICS_PORT``. The
    first binder wins; later children hit ``EADDRINUSE`` and must skip so the
    pool does not crash-loop (XCT-13). Only that child's registry is scraped.

    When ``METRICS_TOKEN`` is set, scrapes must send ``Authorization: Bearer``
    (same contract as the API ``GET /metrics`` route — AUT-06 / XCT-20).
    """
    settings = get_settings()
    if not settings.metrics_enabled:
        return
    app = authorized_metrics_app(settings.metrics_token)
    try:
        httpd = make_server("0.0.0.0", port, app, handler_class=_SilentHandler)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            logger.warning(
                "metrics port %s already bound; skipping in this worker child",
                port,
            )
            return
        raise
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
