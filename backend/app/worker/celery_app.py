"""Celery application used by both the worker and beat processes."""

from celery import Celery

from app.core.config import settings
from app.core.logging import configure_logging
from app.worker.schedule import beat_schedule

configure_logging()

celery_app = Celery(
    "jobnotifier",
    broker=settings.broker_url,
    backend=settings.result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_track_started=True,
    worker_max_tasks_per_child=200,
    broker_connection_retry_on_startup=True,
    beat_schedule=beat_schedule(),
)

# Importing the tasks module registers the task functions on this app.
# Done last to avoid a circular import (tasks imports `celery_app`).
from app.worker import tasks  # noqa: E402,F401
