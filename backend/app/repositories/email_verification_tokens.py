"""Data access for email-verification tokens. Queries only — no business logic."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.email_verification_token import EmailVerificationToken


class EmailVerificationTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, token: EmailVerificationToken) -> EmailVerificationToken:
        self.session.add(token)
        self.session.flush()
        return token

    def get_valid_by_hash(self, token_hash: str, *, now: datetime) -> EmailVerificationToken | None:
        """Return a non-expired token row, or None."""
        return self.session.scalar(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token_hash == token_hash,
                EmailVerificationToken.expires_at > now,
            )
        )

    def delete_for_user(self, user_id: int) -> None:
        self.session.execute(
            delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user_id)
        )
