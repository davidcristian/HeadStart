"""Data access for ApplicationLog."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.application_log import ApplicationLog
from app.models.search import Search
from app.models.seen_job import SeenJob

_PENDING_STATUSES = ("queued", "processing")


class ApplicationLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, log: ApplicationLog) -> ApplicationLog:
        self.session.add(log)
        self.session.flush()
        return log

    def get_for_user(self, log_id: int, user_id: int) -> ApplicationLog | None:
        """Return one application log when it belongs to the user's jobs."""
        stmt = (
            select(ApplicationLog)
            .join(SeenJob, ApplicationLog.seen_job_id == SeenJob.id)
            .join(Search, SeenJob.search_id == Search.id)
            .where(ApplicationLog.id == log_id, Search.user_id == user_id)
            .options(
                joinedload(ApplicationLog.seen_job),
                joinedload(ApplicationLog.tailored_resume_artifact),
            )
        )
        return self.session.scalar(stmt)

    def get_pending_for_job(self, seen_job_id: int) -> ApplicationLog | None:
        """Return an in-flight apply log for a job, if any."""
        stmt = (
            select(ApplicationLog)
            .where(
                ApplicationLog.seen_job_id == seen_job_id,
                ApplicationLog.dry_run.is_(False),
                ApplicationLog.status.in_(_PENDING_STATUSES),
            )
            .order_by(ApplicationLog.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def list_recent_for_user(self, user_id: int, *, limit: int = 100) -> list[ApplicationLog]:
        """Return recent application attempts for jobs owned by the user."""
        stmt = (
            select(ApplicationLog)
            .join(SeenJob, ApplicationLog.seen_job_id == SeenJob.id)
            .join(Search, SeenJob.search_id == Search.id)
            .where(Search.user_id == user_id)
            .options(
                joinedload(ApplicationLog.seen_job),
                joinedload(ApplicationLog.tailored_resume_artifact),
            )
            .order_by(ApplicationLog.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).unique())
