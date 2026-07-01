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
