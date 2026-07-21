"""Inbox reply send audit log persistence."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inbox_reply_send_log import InboxReplySendLog

# Outcomes that consume an hourly/daily auto-reply rate slot.
RATE_SLOT_OUTCOMES = ("sent", "reserved")


class InboxReplySendLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: InboxReplySendLog) -> InboxReplySendLog:
        self.session.add(row)
        self.session.flush()
        return row

    def count_sent_since(self, user_id: int, *, since: datetime) -> int:
        """Count rate-slot rows (sent + in-flight reserved) since a timestamp."""
        count = self.session.scalar(
            select(func.count())
            .select_from(InboxReplySendLog)
            .where(
                InboxReplySendLog.user_id == user_id,
                InboxReplySendLog.outcome.in_(RATE_SLOT_OUTCOMES),
                InboxReplySendLog.created_at >= since,
            )
        )
        return int(count or 0)

    def delete(self, row: InboxReplySendLog) -> None:
        """Remove a reserved rate-slot row after a failed SMTP send."""
        self.session.delete(row)
        self.session.flush()

    def list_for_user(self, user_id: int, *, limit: int | None = 50) -> list[InboxReplySendLog]:
        stmt = (
            select(InboxReplySendLog)
            .where(InboxReplySendLog.user_id == user_id)
            .order_by(InboxReplySendLog.created_at.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))
