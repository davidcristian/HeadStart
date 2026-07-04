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

    def list_for_user(self, user_id: int) -> list[InboxPendingReply]:
        """Return every pending-reply queue row owned by the user."""
        stmt = (
            select(InboxPendingReply)
            .where(InboxPendingReply.user_id == user_id)
            .order_by(InboxPendingReply.created_at.desc())
        )
        return list(self.session.scalars(stmt))

    def claim_due(
        self,
        *,
        now: datetime,
        limit: int = 100,
    ) -> list[InboxPendingReply]:
        """Atomically lease due pending replies so overlapping ticks cannot double-send.

        Selects ``status == 'pending'`` rows whose ``send_after`` has elapsed, locks
        them with ``FOR UPDATE SKIP LOCKED`` on Postgres, and flips each to
        ``sending`` before returning. The caller must commit the lease before SMTP
        so a crash/redelivery cannot re-select the same row. SQLite (tests) has no
        row-level locking; the status flip still blocks a second claim in-process.
        """
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
        if not self._is_sqlite():
            stmt = stmt.with_for_update(skip_locked=True)
        rows = list(self.session.scalars(stmt).unique())
        for row in rows:
            row.status = "sending"
        self.session.flush()
        return rows

    def get_claimed(self, reply_id: int) -> InboxPendingReply | None:
        """Load one leased (``sending``) reply with draft/classification for send."""
        stmt = (
            select(InboxPendingReply)
            .where(
                InboxPendingReply.id == reply_id,
                InboxPendingReply.status == "sending",
            )
            .options(joinedload(InboxPendingReply.draft).joinedload(InboxReplyDraft.classification))
        )
        return self.session.scalars(stmt).unique().first()

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

    def _is_sqlite(self) -> bool:
        return self.session.get_bind().dialect.name == "sqlite"
