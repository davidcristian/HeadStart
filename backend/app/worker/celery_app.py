"""Celery application used by both the worker and beat processes."""

from celery import Celery
from celery.signals import (
    task_postrun,
    task_prerun,
    worker_process_init,
    worker_process_shutdown,
)

from app.core.config import settings
from app.core.logging import configure_logging, reset_request_id
from app.core.metrics import start_metrics_server
from app.core.request_id import bind_celery_task_id
from app.worker.schedule import beat_schedule

configure_logging()

celery_app = Celery(
    "headstart",
    broker=settings.broker_url,
    backend=settings.result_backend,
)

# Soft/hard limits bound hung scrapes and live applies.
# reject_on_worker_lost + acks_late: do not ack a task whose worker died mid-run.
# result_expires: fire-and-forget task payloads must not accumulate in Redis.
_TASK_SOFT_TIME_LIMIT_SECONDS = 600
_TASK_TIME_LIMIT_SECONDS = 660
_RESULT_EXPIRES_SECONDS = 3600

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_soft_time_limit=_TASK_SOFT_TIME_LIMIT_SECONDS,
    task_time_limit=_TASK_TIME_LIMIT_SECONDS,
    result_expires=_RESULT_EXPIRES_SECONDS,
    task_track_started=True,
    worker_max_tasks_per_child=200,
    broker_connection_retry_on_startup=True,
    beat_schedule=beat_schedule(),
)


@worker_process_init.connect
def _start_worker_metrics_server(**_: object) -> None:
    """Expose pipeline metrics from the Celery worker process."""
    start_metrics_server(settings.metrics_port)


@worker_process_shutdown.connect
def _close_playwright_browser(**_: object) -> None:
    """Release the shared headless browser when a worker child exits."""
    from app.scrapers.playwright_browser import close_browser

    close_browser()


@task_prerun.connect
def _bind_task_request_id(task_id: str | None = None, **_: object) -> None:
    """Correlate worker log lines to the Celery task id."""
    bind_celery_task_id(task_id)


@task_postrun.connect
def _clear_task_request_id(**_: object) -> None:
    """Drop the task correlation id so the next task cannot inherit it."""
    reset_request_id()


# Importing the tasks module registers the task functions on this app.
# Done last to avoid a circular import (tasks imports `celery_app`).
from app.worker import tasks  # noqa: E402,F401
