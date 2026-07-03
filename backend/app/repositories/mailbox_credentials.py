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

    def add(self, credential: MailboxCredential) -> MailboxCredential:
        self.session.add(credential)
        self.session.flush()
        return credential

    def delete(self, credential: MailboxCredential) -> None:
        self.session.delete(credential)
