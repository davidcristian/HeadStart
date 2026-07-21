"""Data access for ApplicationLog."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.application_log import ApplicationLog
from app.models.search import Search
from app.models.seen_job import SeenJob


class ApplicationLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, log: ApplicationLog) -> ApplicationLog:
        self.session.add(log)
        self.session.flush()
        return log

    def try_add_pending(self, log: ApplicationLog) -> ApplicationLog | None:
        """Insert a queued apply log, returning None when one is already in-flight.

        Uses a partial unique index on (seen_job_id) for queued/processing live
        applies so concurrent enqueue paths cannot double-submit. Contained in a
        SAVEPOINT so a duplicate rolls back only this insert.
        """
        try:
            with self.session.begin_nested():
                self.session.add(log)
                self.session.flush()
        except IntegrityError:
            return None
        return log

    def count_live_since(self, user_id: int, *, since: datetime) -> int:
        """Count apply attempts that are not dry runs for the user since ``since``."""
        stmt = (
            select(func.count())
            .select_from(ApplicationLog)
            .join(SeenJob, ApplicationLog.seen_job_id == SeenJob.id)
            .join(Search, SeenJob.search_id == Search.id)
            .where(
                Search.user_id == user_id,
                ApplicationLog.dry_run.is_(False),
                ApplicationLog.created_at >= since,
            )
        )
        return int(self.session.scalar(stmt) or 0)

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

    def list_recent_for_user(
        self, user_id: int, *, limit: int | None = 100
    ) -> list[ApplicationLog]:
        """Return application attempts for jobs owned by the user (newest first)."""
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
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt).unique())
