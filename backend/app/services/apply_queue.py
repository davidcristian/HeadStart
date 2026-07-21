"""Queue lease helpers for live auto-apply (claim before employer POST)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.application_log import ApplicationLog
from app.repositories.application_logs import ApplicationLogRepository


def claim_queued_apply(
    session: Session,
    application_log_id: int,
    user_id: int,
    job_id: int,
) -> ApplicationLog | None:
    """Lease a queued apply (queued → processing) before the external submit.

    Commit this in its own transaction so an ``acks_late`` redelivery after a
    mid-submit crash sees ``processing`` and skips instead of double-posting
    to the employer.
    """
    logs = ApplicationLogRepository(session)
    log = logs.get_for_user(application_log_id, user_id)
    if log is None or log.seen_job_id != job_id:
        raise NotFoundError(f"Application log {application_log_id} not found")
    if log.status != "queued":
        return None
    log.status = "processing"
    session.flush()
    return log


def fail_queued_apply(session: Session, application_log_id: int, error: str) -> None:
    """Mark a queued/processing apply as failed when the worker cannot complete it."""
    log = session.get(ApplicationLog, application_log_id)
    if log is None or log.status not in ("queued", "processing"):
        return
    log.status = "failed"
    log.error = error
    session.flush()
