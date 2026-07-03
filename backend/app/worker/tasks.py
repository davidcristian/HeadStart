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
from app.services.ghost_detection import GhostDetectionService
from app.services.inbox_orchestration import InboxOrchestrationService
from app.services.pending_replies import PendingReplyService
from app.services.pipeline import PipelineService
from app.worker.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.worker.tasks.run_search", bind=True, max_retries=0)
def run_search(self: object, search_id: int) -> dict[str, object]:
    """Run one search's pipeline (scrape -> dedupe -> notify -> record)."""
    pending_applies: list = []
    with session_scope() as session:
        result = PipelineService(session).run(search_id)
        pending_applies = list(result.pending_auto_applies)

    for queued in pending_applies:
        apply_to_job_task.delay(
            queued.application_log_id,
            queued.user_id,
            queued.job_id,
            queued.cover_letter,
        )

    logger.info(
        "run_search %s: found=%d filtered=%d new=%d notified=%d queued=%d failed=%d auto_apply=%d",
        result.search_id,
        result.found,
        result.filtered,
        result.new,
        result.notified,
        result.queued,
        result.failed,
        result.auto_apply_queued,
    )
    payload = asdict(result)
    payload.pop("pending_auto_applies", None)
    return payload


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
    tailored_resume_b64: str | None = None,
) -> dict[str, object]:
    """Run one queued live auto-apply in the worker."""
    try:
        with session_scope() as session:
            result = ApplyService(session).apply_to_job(
                user_id,
                job_id,
                dry_run=False,
                cover_letter=cover_letter,
                tailored_resume_b64=tailored_resume_b64,
                application_log_id=application_log_id,
            )
    except Exception as exc:
        # Persist failure in a separate transaction: session_scope rolls back on
        # exception, so marking failed inside the same scope would be lost.
        with session_scope() as session:
            ApplyService(session).fail_queued_apply(application_log_id, str(exc))
        logger.exception(
            "apply_to_job failed log=%s job=%s user=%s",
            application_log_id,
            job_id,
            user_id,
        )
        return {
            "application_log_id": application_log_id,
            "status": "failed",
            "error": str(exc),
        }

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


@celery_app.task(name="app.worker.tasks.detect_ghosted_applications")
def detect_ghosted_applications() -> dict[str, int]:
    """Beat tick: email self-summaries for applications past the ghost silence window."""
    with session_scope() as session:
        result = GhostDetectionService(session).process_due(now=utcnow())

    return {
        "checked": result.checked,
        "ghosted": result.ghosted,
        "skipped": result.skipped,
        "failed": result.failed,
    }


@celery_app.task(name="app.worker.tasks.process_inbox_messages")
def process_inbox_messages() -> dict[str, int]:
    """Beat tick: poll mailboxes, classify new messages, and route when configured."""
    with session_scope() as session:
        result = InboxOrchestrationService(session).process_due()

    return {
        "users": result.users,
        "fetched": result.fetched,
        "classified": result.classified,
        "skipped": result.skipped,
        "ignored": result.ignored,
        "failed": result.failed,
    }


@celery_app.task(name="app.worker.tasks.process_pending_replies")
def process_pending_replies() -> dict[str, int]:
    """Beat tick: send recruiter replies whose human-like delay has elapsed."""
    with session_scope() as session:
        result = PendingReplyService(session).process_due(now=utcnow())

    return {
        "checked": result.checked,
        "sent": result.sent,
        "failed": result.failed,
        "skipped": result.skipped,
    }
