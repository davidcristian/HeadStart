"""Service-level auth edge cases (error branches not reached via HTTP tests)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_password_reset_token,
)
from app.models.base import utcnow
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.repositories.email_verification_tokens import EmailVerificationTokenRepository
from app.repositories.password_reset_tokens import PasswordResetTokenRepository
from app.repositories.users import UserRepository
from app.schemas.auth import (
    LoginRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.services.auth import AuthService


def _user(db_session: Session, *, email: str = "auth@example.com", active: bool = True) -> User:
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        is_active=active,
    )
    return UserRepository(db_session).add(user)


def test_login_unknown_email_rejected(db_session: Session) -> None:
    with pytest.raises(ValidationError, match="Invalid email or password"):
        AuthService(db_session).login(
            LoginRequest(email="missing@example.com", password="password123")
        )


def test_login_inactive_user_rejected(db_session: Session) -> None:
    _user(db_session, email="inactive@example.com", active=False)
    with pytest.raises(ValidationError, match="Invalid email or password"):
        AuthService(db_session).login(
            LoginRequest(email="inactive@example.com", password="password123")
        )


def test_login_active_user_succeeds(db_session: Session) -> None:
    _user(db_session, email="ok@example.com")
    tokens = AuthService(db_session).login(
        LoginRequest(email="ok@example.com", password="password123")
    )
    assert tokens.access_token
    assert tokens.refresh_token


def test_refresh_invalid_token_rejected(db_session: Session) -> None:
    with pytest.raises(ValidationError):
        AuthService(db_session).refresh("garbage-token")


def test_refresh_inactive_user_rejected(db_session: Session) -> None:
    user = _user(db_session, email="ref@example.com")
    token = create_refresh_token(user.id, version=user.token_version)
    user.is_active = False
    db_session.flush()
    with pytest.raises(ValidationError, match="no longer active"):
        AuthService(db_session).refresh(token)


def test_refresh_stale_version_rejected(db_session: Session) -> None:
    user = _user(db_session, email="ver@example.com")
    token = create_refresh_token(user.id, version=user.token_version)
    user.token_version += 1
    db_session.flush()
    with pytest.raises(ValidationError, match="no longer valid"):
        AuthService(db_session).refresh(token)


def test_me_missing_user_raises(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        AuthService(db_session).me(999999)


def test_reset_password_inactive_user_rejected(db_session: Session) -> None:
    user = _user(db_session, email="rst@example.com")
    raw = "reset-raw-token"
    PasswordResetTokenRepository(db_session).add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_password_reset_token(raw),
            expires_at=utcnow() + timedelta(minutes=30),
        )
    )
    user.is_active = False
    db_session.flush()

    with pytest.raises(ValidationError, match="Invalid or expired"):
        AuthService(db_session).reset_password(
            ResetPasswordRequest(token=raw, password="newpassword123")
        )


def test_verify_email_inactive_user_rejected(db_session: Session) -> None:
    user = _user(db_session, email="vrf@example.com")
    raw = "verify-raw-token"
    EmailVerificationTokenRepository(db_session).add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_password_reset_token(raw),
            expires_at=utcnow() + timedelta(minutes=30),
        )
    )
    user.is_active = False
    db_session.flush()

    with pytest.raises(ValidationError, match="Invalid or expired"):
        AuthService(db_session).verify_email(VerifyEmailRequest(token=raw))


def test_verify_email_already_verified_is_idempotent(db_session: Session) -> None:
    user = _user(db_session, email="already@example.com")
    already = utcnow() - timedelta(days=1)
    user.email_verified_at = already
    db_session.flush()

    raw = "verify-again-token"
    EmailVerificationTokenRepository(db_session).add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_password_reset_token(raw),
            expires_at=utcnow() + timedelta(minutes=30),
        )
    )
    db_session.flush()

    result = AuthService(db_session).verify_email(VerifyEmailRequest(token=raw))
    # Timestamp is not overwritten when already verified.
    assert result.email_verified_at == already


def test_register_issues_verification_email(db_session: Session) -> None:
    from app.schemas.auth import RegisterRequest

    with (
        patch("app.services.auth.send_verification_email") as send_mail,
        patch(
            "app.services.auth.generate_password_reset_token",
            return_value="verif-token",
        ),
    ):
        user = AuthService(db_session).register(
            RegisterRequest(email="reg@example.com", password="password123")
        )

    assert user.email == "reg@example.com"
    send_mail.assert_called_once()


def test_reset_password_success_bumps_token_version(db_session: Session) -> None:
    user = _user(db_session, email="pw@example.com")
    original_version = user.token_version
    old_access = create_access_token(user.id, version=user.token_version)
    assert old_access  # sanity

    raw = "reset-ok-token"
    PasswordResetTokenRepository(db_session).add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_password_reset_token(raw),
            expires_at=utcnow() + timedelta(minutes=30),
        )
    )
    db_session.flush()

    AuthService(db_session).reset_password(
        ResetPasswordRequest(token=raw, password="brand-new-pass")
    )
    db_session.refresh(user)
    assert user.token_version != original_version
