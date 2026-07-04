"""Inbox classification persistence."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.inbox_classification import InboxClassification


class InboxClassificationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id_for_user(
        self, user_id: int, classification_id: int
    ) -> InboxClassification | None:
        return self.session.scalar(
            select(InboxClassification)
            .where(
                InboxClassification.user_id == user_id,
                InboxClassification.id == classification_id,
            )
            .options(joinedload(InboxClassification.seen_job))
        )

    def get_by_user_and_uid(self, user_id: int, message_uid: int) -> InboxClassification | None:
        return self.session.scalar(
            select(InboxClassification)
            .where(
                InboxClassification.user_id == user_id,
                InboxClassification.message_uid == message_uid,
            )
            .options(joinedload(InboxClassification.seen_job))
        )

    def list_for_user(self, user_id: int, *, limit: int | None = 50) -> list[InboxClassification]:
        stmt = (
            select(InboxClassification)
            .where(InboxClassification.user_id == user_id)
            .options(joinedload(InboxClassification.seen_job))
            .order_by(InboxClassification.created_at.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def add(self, row: InboxClassification) -> InboxClassification:
        self.session.add(row)
        self.session.flush()
        return row

    def max_message_uid_for_user(self, user_id: int) -> int | None:
        """Highest classified mailbox UID for poll-cursor bootstrap."""
        value = self.session.scalar(
            select(func.max(InboxClassification.message_uid)).where(
                InboxClassification.user_id == user_id
            )
        )
        return int(value) if value is not None else None

    def latest_draftable_by_seen_job_ids(
        self, user_id: int, seen_job_ids: list[int]
    ) -> dict[int, InboxClassification]:
        """Newest follow-up/general classification per job for reply drafting."""
        if not seen_job_ids:
            return {}
        stmt = (
            select(InboxClassification)
            .where(
                InboxClassification.user_id == user_id,
                InboxClassification.seen_job_id.in_(seen_job_ids),
                InboxClassification.label.in_(("follow_up", "general")),
            )
            .order_by(InboxClassification.seen_job_id, InboxClassification.created_at.desc())
        )
        rows = list(self.session.scalars(stmt))
        latest: dict[int, InboxClassification] = {}
        for row in rows:
            if row.seen_job_id is not None and row.seen_job_id not in latest:
                latest[row.seen_job_id] = row
        return latest
