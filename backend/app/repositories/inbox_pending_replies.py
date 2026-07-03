"""Inbox pending reply queue persistence."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.inbox_pending_reply import InboxPendingReply
from app.models.inbox_reply_draft import InboxReplyDraft


class InboxPendingReplyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_draft(self, user_id: int, draft_id: int) -> InboxPendingReply | None:
        return self.session.scalar(
            select(InboxPendingReply).where(
                InboxPendingReply.user_id == user_id,
                InboxPendingReply.inbox_reply_draft_id == draft_id,
            )
        )

    def list_due(
        self,
        *,
        now: datetime,
        limit: int = 100,
    ) -> list[InboxPendingReply]:
        stmt = (
            select(InboxPendingReply)
            .where(
                InboxPendingReply.status == "pending",
                InboxPendingReply.send_after <= now,
            )
            .options(joinedload(InboxPendingReply.draft).joinedload(InboxReplyDraft.classification))
            .order_by(InboxPendingReply.send_after)
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def add(self, row: InboxPendingReply) -> InboxPendingReply:
        self.session.add(row)
        self.session.flush()
        return row

    def cancel_for_draft(self, user_id: int, draft_id: int) -> None:
        row = self.get_by_draft(user_id, draft_id)
        if row is None or row.status in {"sent", "cancelled"}:
            return
        row.status = "cancelled"
        row.error = None
        self.session.flush()
