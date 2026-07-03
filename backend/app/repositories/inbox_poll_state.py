"""Inbox poll cursor persistence."""

from sqlalchemy import select
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
        """Advance the poll cursor after a successful fetch/classify pass."""
        row = self.get_for_user(user_id)
        if row is None:
            row = InboxPollState(user_id=user_id, last_polled_uid=last_polled_uid)
            self.session.add(row)
        else:
            row.last_polled_uid = last_polled_uid
        self.session.flush()
        return row
