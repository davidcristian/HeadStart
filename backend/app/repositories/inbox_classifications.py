"""Inbox classification persistence."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.inbox_classification import InboxClassification


class InboxClassificationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_user_and_uid(self, user_id: int, message_uid: int) -> InboxClassification | None:
        return self.session.scalar(
            select(InboxClassification)
            .where(
                InboxClassification.user_id == user_id,
                InboxClassification.message_uid == message_uid,
            )
            .options(joinedload(InboxClassification.seen_job))
        )

    def list_for_user(self, user_id: int, *, limit: int = 50) -> list[InboxClassification]:
        stmt = (
            select(InboxClassification)
            .where(InboxClassification.user_id == user_id)
            .options(joinedload(InboxClassification.seen_job))
            .order_by(InboxClassification.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def add(self, row: InboxClassification) -> InboxClassification:
        self.session.add(row)
        self.session.flush()
        return row
