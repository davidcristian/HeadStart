"""Password-reset helpers for AuthService (keeps auth.py under the LOC cap)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.auth_events import log_auth_event
from app.core.config import settings
from app.core.email import send_password_reset_email
from app.core.exceptions import ValidationError
from app.core.rate_limit import FORGOT_EMAIL, enforce_rate_limit
from app.core.security import (
    generate_password_reset_token,
    hash_password,
    hash_url_token,
)
from app.models.base import utcnow
from app.models.password_reset_token import PasswordResetToken
from app.repositories.password_reset_tokens import PasswordResetTokenRepository
from app.repositories.users import UserRepository
from app.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest

_PASSWORD_RESET_SENT_MESSAGE = (
    "If an account exists for that email, a password reset link has been sent."
)

# Matches BackgroundTasks.add_task / Celery-style deferral: call(fn, **kwargs).
EmailScheduler = Callable[..., Any]


def request_password_reset(
    session: Session,
    data: ForgotPasswordRequest,
    *,
    ip_address: str | None = None,
    schedule_email: EmailScheduler | None = None,
) -> str:
    """Issue a reset token and email it. Always returns the same message.

    Token generation/hashing always runs (even for unknown emails) so response
    work matches the issued path before any mail I/O. When ``schedule_email`` is
    provided (API BackgroundTasks), SMTP runs after the response so timing cannot
    enumerate accounts via the SMTP round-trip (AUT-26).
    """
    email = data.email.lower()
    # Cap outbound reset mail per address even when the account is missing,
    # so the route cannot be used to email-bomb a known inbox.
    enforce_rate_limit(f"auth:forgot:email_issue:{email}", FORGOT_EMAIL)
    users = UserRepository(session)
    reset_tokens = PasswordResetTokenRepository(session)
    user = users.get_by_email(email)

    # Burn the same crypto cost on the miss path (mirrors login's placeholder bcrypt).
    raw_token = generate_password_reset_token()
    token_hash = hash_url_token(raw_token)

    if user is None or not user.is_active:
        log_auth_event(
            "password_reset_requested",
            email=email,
            ip_address=ip_address,
            issued=False,
        )
        return _PASSWORD_RESET_SENT_MESSAGE

    expires_at = utcnow() + timedelta(minutes=settings.password_reset_expire_minutes)
    reset_tokens.delete_for_user(user.id)
    reset_tokens.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )

    reset_url = f"{settings.frontend_base_url.rstrip('/')}/reset-password?token={raw_token}"
    if schedule_email is not None:
        schedule_email(
            send_password_reset_email,
            to_email=user.email,
            reset_url=reset_url,
        )
    else:
        send_password_reset_email(to_email=user.email, reset_url=reset_url)
    log_auth_event(
        "password_reset_requested",
        email=user.email,
        user_id=user.id,
        ip_address=ip_address,
        issued=True,
    )
    return _PASSWORD_RESET_SENT_MESSAGE


def reset_password(
    session: Session,
    data: ResetPasswordRequest,
    *,
    ip_address: str | None = None,
) -> None:
    """Set a new password from a valid reset token and invalidate sessions."""
    users = UserRepository(session)
    reset_tokens = PasswordResetTokenRepository(session)
    token_hash = hash_url_token(data.token)
    now = utcnow()
    row = reset_tokens.claim_valid_by_hash(token_hash, now=now)
    if row is None:
        raise ValidationError("Invalid or expired reset link. Request a new one.")
    # Persist the consume before any path that may raise so single-use does not
    # depend on a later delete surviving the request transaction (DAT-18), and
    # so an inactive/missing user cannot leave a replayable link (AUT-30).
    session.commit()

    user = users.get(row.user_id)
    if user is None or not user.is_active:
        raise ValidationError("Invalid or expired reset link. Request a new one.")

    users.update_password(user, hash_password(data.password))
    # Terminate sessions that may have been opened with a compromised
    # credential: bump the token version so outstanding access/refresh
    # tokens (which carry the old `ver`) stop validating.
    users.bump_token_version(user)
    users.bump_feed_token_version(user)
    reset_tokens.delete_for_user(user.id)
    log_auth_event(
        "password_reset_completed",
        email=user.email,
        user_id=user.id,
        ip_address=ip_address,
    )
    log_auth_event(
        "session_invalidated",
        email=user.email,
        user_id=user.id,
        ip_address=ip_address,
        reason="password_reset",
    )
