"""Mailbox credential persistence."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mailbox_credential import MailboxCredential


class MailboxCredentialRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_user(self, user_id: int) -> MailboxCredential | None:
        return self.session.scalar(
            select(MailboxCredential).where(MailboxCredential.user_id == user_id)
        )

    def get_for_user_for_update(self, user_id: int) -> MailboxCredential | None:
        """Fetch the user's mailbox credential holding a row lock (Postgres).

        Serializes OAuth token refresh so concurrent workers cannot rotate the
        same refresh_token. SQLite (tests) has no row locking, so it returns the
        unlocked row.
        """
        if self._is_sqlite():
            return self.get_for_user(user_id)
        stmt = (
            select(MailboxCredential).where(MailboxCredential.user_id == user_id).with_for_update()
        )
        return self.session.scalar(stmt)

    def add(self, credential: MailboxCredential) -> MailboxCredential:
        self.session.add(credential)
        self.session.flush()
        return credential

    def delete(self, credential: MailboxCredential) -> None:
        self.session.delete(credential)

    def list_enabled(self) -> list[MailboxCredential]:
        """Return enabled mailbox credentials for inbox orchestration."""
        stmt = select(MailboxCredential).where(MailboxCredential.enabled.is_(True))
        return list(self.session.scalars(stmt))

    def _is_sqlite(self) -> bool:
        return self.session.get_bind().dialect.name == "sqlite"
