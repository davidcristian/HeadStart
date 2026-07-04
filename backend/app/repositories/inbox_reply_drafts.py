"""Inbox reply draft persistence."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.inbox_reply_draft import InboxReplyDraft


class InboxReplyDraftRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_classification(self, user_id: int, classification_id: int) -> InboxReplyDraft | None:
        return self.session.scalar(
            select(InboxReplyDraft).where(
                InboxReplyDraft.user_id == user_id,
                InboxReplyDraft.inbox_classification_id == classification_id,
            )
        )

    def list_for_user(
        self,
        user_id: int,
        *,
        seen_job_id: int | None = None,
        limit: int | None = 50,
    ) -> list[InboxReplyDraft]:
        stmt = (
            select(InboxReplyDraft)
            .where(InboxReplyDraft.user_id == user_id)
            .options(joinedload(InboxReplyDraft.classification))
        )
        if seen_job_id is not None:
            stmt = stmt.where(InboxReplyDraft.seen_job_id == seen_job_id)
        stmt = stmt.order_by(InboxReplyDraft.created_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def latest_by_seen_job_ids(
        self, user_id: int, seen_job_ids: list[int]
    ) -> dict[int, InboxReplyDraft]:
        """Return the newest draft per seen_job_id for pipeline enrichment."""
        if not seen_job_ids:
            return {}
        stmt = (
            select(InboxReplyDraft)
            .where(
                InboxReplyDraft.user_id == user_id,
                InboxReplyDraft.seen_job_id.in_(seen_job_ids),
            )
            .order_by(InboxReplyDraft.seen_job_id, InboxReplyDraft.created_at.desc())
        )
        rows = list(self.session.scalars(stmt))
        latest: dict[int, InboxReplyDraft] = {}
        for row in rows:
            if row.seen_job_id is not None and row.seen_job_id not in latest:
                latest[row.seen_job_id] = row
        return latest

    def add(self, row: InboxReplyDraft) -> InboxReplyDraft:
        self.session.add(row)
        self.session.flush()
        return row

    def delete(self, row: InboxReplyDraft) -> None:
        self.session.delete(row)
        self.session.flush()

    def count_for_user(self, user_id: int) -> int:
        value = self.session.scalar(
            select(func.count())
            .select_from(InboxReplyDraft)
            .where(InboxReplyDraft.user_id == user_id)
        )
        return int(value or 0)
