"""Query-only data access for password-reset tokens. Holds no business logic."""

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
        """Return a non-expired, unused token row, or None."""
        return self.session.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.expires_at > now,
                PasswordResetToken.used_at.is_(None),
            )
        )

    def claim_valid_by_hash(self, token_hash: str, *, now: datetime) -> PasswordResetToken | None:
        """Atomically mark a non-expired unused token consumed and return it.

        Single-use must not depend on a later best-effort delete. On
        Postgres the row is locked with FOR UPDATE so concurrent claims cannot
        both succeed; SQLite (tests) still serializes via the used_at stamp.
        """
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.expires_at > now,
            PasswordResetToken.used_at.is_(None),
        )
        if not self._is_sqlite():
            stmt = stmt.with_for_update()
        row = self.session.scalar(stmt)
        if row is None:
            return None
        row.used_at = now
        self.session.flush()
        return row

    def delete_for_user(self, user_id: int) -> None:
        self.session.execute(
            delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
        )

    def _is_sqlite(self) -> bool:
        return self.session.get_bind().dialect.name == "sqlite"
