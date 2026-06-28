"""Data access for password-reset tokens. Queries only — no business logic."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.password_reset_token import PasswordResetToken


class PasswordResetTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, token: PasswordResetToken) -> PasswordResetToken:
        self.session.add(token)
        self.session.flush()
        return token

    def get_valid_by_hash(self, token_hash: str, *, now: datetime) -> PasswordResetToken | None:
        """Return a non-expired token row, or None."""
        return self.session.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.expires_at > now,
            )
        )

    def delete_for_user(self, user_id: int) -> None:
        self.session.execute(
            delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
        )
