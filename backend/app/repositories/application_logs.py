"""Data access for ApplicationLog."""

from __future__ import annotations

from sqlalchemy import select
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

    def list_recent_for_user(self, user_id: int, *, limit: int = 100) -> list[ApplicationLog]:
        """Return recent application attempts for jobs owned by the user."""
        stmt = (
            select(ApplicationLog)
            .join(SeenJob, ApplicationLog.seen_job_id == SeenJob.id)
            .join(Search, SeenJob.search_id == Search.id)
            .where(Search.user_id == user_id)
            .options(joinedload(ApplicationLog.seen_job))
            .order_by(ApplicationLog.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).unique())
