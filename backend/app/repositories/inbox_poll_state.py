"""Inbox poll cursor persistence."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.inbox_poll_state import InboxPollState


class InboxPollStateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_user(self, user_id: int) -> InboxPollState | None:
        return self.session.scalar(select(InboxPollState).where(InboxPollState.user_id == user_id))

    def get_last_polled_uid(self, user_id: int) -> int | None:
        row = self.get_for_user(user_id)
        return row.last_polled_uid if row is not None else None

    def upsert_last_polled_uid(self, user_id: int, last_polled_uid: int) -> InboxPollState:
        """Advance the poll cursor after a successful fetch/classify pass.

        First-time inserts use a SAVEPOINT so a concurrent first poll that lost
        the unique(user_id) race rolls back only the insert, then updates the
        winning row.
        """
        row = self.get_for_user(user_id)
        if row is not None:
            row.last_polled_uid = last_polled_uid
            self.session.flush()
            return row

        row = InboxPollState(user_id=user_id, last_polled_uid=last_polled_uid)
        try:
            with self.session.begin_nested():
                self.session.add(row)
                self.session.flush()
        except IntegrityError:
            existing = self.get_for_user(user_id)
            if existing is None:
                raise
            existing.last_polled_uid = last_polled_uid
            self.session.flush()
            return existing
        return row
