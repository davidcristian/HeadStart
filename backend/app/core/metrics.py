"""Prometheus metrics for scrape, notification, and scheduler observability."""

from __future__ import annotations

from typing import Literal

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.core.config import get_settings

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


def record_digest_flush(status: Literal["success", "error"]) -> None:
    """Record a digest batch flush."""
    if not get_settings().metrics_enabled:
        return
    DIGEST_FLUSHES.labels(status=status).inc()


def record_scheduler_enqueued(count: int) -> None:
    """Record how many due searches were enqueued on a beat tick."""
    if not get_settings().metrics_enabled or count <= 0:
        return
    SCHEDULER_SEARCHES_ENQUEUED.inc(count)


def render_metrics() -> tuple[bytes, str]:
    """Return Prometheus exposition payload and content type."""
    return generate_latest(), CONTENT_TYPE_LATEST


def start_metrics_server(port: int) -> None:
    """Expose /metrics on a background HTTP server (worker processes)."""
    if not get_settings().metrics_enabled:
        return
    from prometheus_client import start_http_server

    start_http_server(port)
