"""Data access for DataRequestLog."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_request_log import DataRequestLog


class DataRequestLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, log: DataRequestLog) -> DataRequestLog:
        self.session.add(log)
        self.session.flush()
        return log

    def list_recent(self, *, limit: int = 100) -> list[DataRequestLog]:
        """Return the most recent GDPR data requests across all users."""
        stmt = select(DataRequestLog).order_by(DataRequestLog.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))

    def redact_for_erasure(self, user_id: int, *, email_pseudonym: str) -> int:
        """Strip recoverable PII from prior GDPR audit rows for a user being erased."""
        stmt = select(DataRequestLog).where(DataRequestLog.user_id == user_id)
        rows = list(self.session.scalars(stmt))
        for row in rows:
            row.user_id = None
            row.user_email = email_pseudonym
            row.ip_address = None
            row.user_agent = None
        self.session.flush()
        return len(rows)
