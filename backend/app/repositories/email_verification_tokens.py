"""Query-only data access for email-verification tokens. Holds no business logic."""

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
        """Return a non-expired, unused token row, or None."""
        return self.session.scalar(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token_hash == token_hash,
                EmailVerificationToken.expires_at > now,
                EmailVerificationToken.used_at.is_(None),
            )
        )

    def claim_valid_by_hash(
        self, token_hash: str, *, now: datetime
    ) -> EmailVerificationToken | None:
        """Atomically mark a non-expired unused token consumed and return it.

        Single-use must not depend on a later best-effort delete. On
        Postgres the row is locked with FOR UPDATE so concurrent claims cannot
        both succeed; SQLite (tests) still serializes via the used_at stamp.
        """
        stmt = select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.expires_at > now,
            EmailVerificationToken.used_at.is_(None),
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
            delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user_id)
        )

    def _is_sqlite(self) -> bool:
        return self.session.get_bind().dialect.name == "sqlite"
