"""Celery tasks: glue between the scheduler and the pipeline service.

These are intentionally thin. All real logic lives in `app.services`.
"""

from __future__ import annotations

from dataclasses import asdict

from app.core.db import session_scope
from app.core.logging import get_logger
from app.core.metrics import record_scheduler_enqueued
from app.models.base import utcnow
from app.repositories.searches import SearchRepository
from app.services.apply import ApplyService
from app.services.digest import DigestService
from app.services.pipeline import PipelineService
from app.worker.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.worker.tasks.run_search", bind=True, max_retries=0)
def run_search(self: object, search_id: int) -> dict[str, object]:
    """Run one search's pipeline (scrape -> dedupe -> notify -> record)."""
    with session_scope() as session:
        result = PipelineService(session).run(search_id)
    logger.info(
        "run_search %s: found=%d filtered=%d new=%d notified=%d queued=%d failed=%d",
        result.search_id,
        result.found,
        result.filtered,
        result.new,
        result.notified,
        result.queued,
        result.failed,
    )
    return asdict(result)


@celery_app.task(name="app.worker.tasks.enqueue_due_searches")
def enqueue_due_searches() -> int:
    """Beat tick: enqueue every search whose next_run_at is in the past.

    This is also the startup catch-up mechanism: any search left overdue while
    the system was down is picked up on the first tick. Because each run
    reschedules from *now*, a long downtime produces a single catch-up run per
    search, not one per missed interval.
    """
    with session_scope() as session:
        due_ids = [s.id for s in SearchRepository(session).due(utcnow())]

    for search_id in due_ids:
        run_search.delay(search_id)

    record_scheduler_enqueued(len(due_ids))
    if due_ids:
        logger.info("enqueued %d due search(es): %s", len(due_ids), due_ids)
    return len(due_ids)


@celery_app.task(name="app.worker.tasks.apply_to_job", bind=True, max_retries=0)
def apply_to_job_task(
    self: object,
    application_log_id: int,
    user_id: int,
    job_id: int,
    cover_letter: str | None,
) -> dict[str, object]:
    """Run one queued live auto-apply in the worker."""
    with session_scope() as session:
        service = ApplyService(session)
        try:
            result = service.apply_to_job(
                user_id,
                job_id,
                dry_run=False,
                cover_letter=cover_letter,
                application_log_id=application_log_id,
            )
        except Exception as exc:
            service.fail_queued_apply(application_log_id, str(exc))
            logger.exception(
                "apply_to_job failed log=%s job=%s user=%s",
                application_log_id,
                job_id,
                user_id,
            )
            raise

    logger.info(
        "apply_to_job log=%s job=%s user=%s status=%s",
        application_log_id,
        job_id,
        user_id,
        result.status,
    )
    return {
        "application_log_id": application_log_id,
        "status": result.status,
        "error": result.error,
    }


@celery_app.task(name="app.worker.tasks.flush_due_digests")
def flush_due_digests() -> int:
    """Beat tick: send batched digest notifications whose interval has elapsed."""
    with session_scope() as session:
        flushed = DigestService(session).flush_due(utcnow())

    if flushed:
        logger.info("flushed %d digest search(es)", flushed)
    return flushed
