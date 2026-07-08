"""Regression tests for atomic reset/verify token consume (DAT-18)."""

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.core.security import hash_password_reset_token
from app.models.base import utcnow
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.repositories.email_verification_tokens import EmailVerificationTokenRepository
from app.repositories.password_reset_tokens import PasswordResetTokenRepository
from app.repositories.users import UserRepository
from app.schemas.auth import ResetPasswordRequest, VerifyEmailRequest
from app.services.auth import AuthService


def _user(session: Session, *, email: str) -> User:
    return UserRepository(session).add(
        User(email=email, password_hash="hash", is_admin=False, is_active=True)
    )


def test_claim_valid_by_hash_marks_password_reset_used(db_session: Session) -> None:
    user = _user(db_session, email="claim-reset@example.com")
    raw = "claim-reset-token"
    token_hash = hash_password_reset_token(raw)
    repo = PasswordResetTokenRepository(db_session)
    repo.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(minutes=30),
        )
    )
    db_session.flush()

    now = utcnow()
    claimed = repo.claim_valid_by_hash(token_hash, now=now)
    assert claimed is not None
    assert claimed.used_at == now
    assert repo.get_valid_by_hash(token_hash, now=now) is None
    assert repo.claim_valid_by_hash(token_hash, now=now) is None


def test_claim_valid_by_hash_marks_email_verification_used(db_session: Session) -> None:
    user = _user(db_session, email="claim-verify@example.com")
    raw = "claim-verify-token"
    token_hash = hash_password_reset_token(raw)
    repo = EmailVerificationTokenRepository(db_session)
    repo.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(minutes=30),
        )
    )
    db_session.flush()

    now = utcnow()
    claimed = repo.claim_valid_by_hash(token_hash, now=now)
    assert claimed is not None
    assert claimed.used_at == now
    assert repo.get_valid_by_hash(token_hash, now=now) is None
    assert repo.claim_valid_by_hash(token_hash, now=now) is None


def test_reset_password_rejects_replay_after_success(db_session: Session) -> None:
    user = _user(db_session, email="replay-reset@example.com")
    raw = "replay-reset-token"
    PasswordResetTokenRepository(db_session).add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_password_reset_token(raw),
            expires_at=utcnow() + timedelta(minutes=30),
        )
    )
    db_session.flush()

    AuthService(db_session).reset_password(
        ResetPasswordRequest(token=raw, password="brand-new-pass-99")
    )

    with pytest.raises(ValidationError, match="Invalid or expired"):
        AuthService(db_session).reset_password(
            ResetPasswordRequest(token=raw, password="another-pass-99")
        )


def test_verify_email_rejects_replay_after_success(db_session: Session) -> None:
    user = _user(db_session, email="replay-verify@example.com")
    raw = "replay-verify-token"
    EmailVerificationTokenRepository(db_session).add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_password_reset_token(raw),
            expires_at=utcnow() + timedelta(minutes=30),
        )
    )
    db_session.flush()

    AuthService(db_session).verify_email(VerifyEmailRequest(token=raw))

    with pytest.raises(ValidationError, match="Invalid or expired"):
        AuthService(db_session).verify_email(VerifyEmailRequest(token=raw))


def test_claim_password_reset_uses_for_update_when_not_sqlite(db_session: Session) -> None:
    """Force the Postgres FOR UPDATE branch (SQLite silently drops the clause)."""
    user = _user(db_session, email="for-update-reset@example.com")
    token_hash = hash_password_reset_token("for-update-reset")
    repo = PasswordResetTokenRepository(db_session)
    repo.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(minutes=30),
        )
    )
    db_session.flush()
    repo._is_sqlite = lambda: False  # type: ignore[method-assign]

    claimed = repo.claim_valid_by_hash(token_hash, now=utcnow())
    assert claimed is not None
    assert claimed.used_at is not None


def test_claim_email_verification_uses_for_update_when_not_sqlite(db_session: Session) -> None:
    """Force the Postgres FOR UPDATE branch (SQLite silently drops the clause)."""
    user = _user(db_session, email="for-update-verify@example.com")
    token_hash = hash_password_reset_token("for-update-verify")
    repo = EmailVerificationTokenRepository(db_session)
    repo.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(minutes=30),
        )
    )
    db_session.flush()
    repo._is_sqlite = lambda: False  # type: ignore[method-assign]

    claimed = repo.claim_valid_by_hash(token_hash, now=utcnow())
    assert claimed is not None
    assert claimed.used_at is not None


def test_claim_password_reset_compiles_for_update_for_postgres() -> None:
    """Postgres claim SQL must lock the row so concurrent claims cannot both succeed."""
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    now = utcnow()
    stmt = (
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == "abc",
            PasswordResetToken.expires_at > now,
            PasswordResetToken.used_at.is_(None),
        )
        .with_for_update()
    )
    compiled = str(
        stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "FOR UPDATE" in compiled.upper()


def test_claim_valid_by_hash_returns_none_when_missing(db_session: Session) -> None:
    now = utcnow()
    assert PasswordResetTokenRepository(db_session).claim_valid_by_hash("missing", now=now) is None
    assert (
        EmailVerificationTokenRepository(db_session).claim_valid_by_hash("missing", now=now) is None
    )
