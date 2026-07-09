"""Authentication business logic: registration, login, token refresh, password reset."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.auth_events import log_auth_event
from app.core.config import settings
from app.core.email import send_verification_email
from app.core.exceptions import NotFoundError, ValidationError
from app.core.rate_limit import limit_verification_email_issue
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_password_reset_token,
    hash_url_token,
    verify_password,
)
from app.models.base import utcnow
from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User
from app.repositories.email_verification_tokens import EmailVerificationTokenRepository
from app.repositories.password_reset_tokens import PasswordResetTokenRepository
from app.repositories.users import UserRepository
from app.schemas.auth import (
    DeleteAccountRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserDataExport,
    VerifyEmailRequest,
)
from app.services.auth_account import delete_user_account, export_user_data
from app.services.auth_password import (
    request_password_reset as issue_password_reset,
)
from app.services.auth_password import (
    reset_password as apply_password_reset,
)
from app.services.auth_register import register_account

_VERIFICATION_SENT_MESSAGE = (
    "If your account is not yet verified, a verification link has been sent."
)


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = UserRepository(session)
        self.reset_tokens = PasswordResetTokenRepository(session)
        self.verification_tokens = EmailVerificationTokenRepository(session)

    def register(
        self,
        data: RegisterRequest,
        *,
        ip_address: str | None = None,
    ) -> User | None:
        """Create an account when the email is free; never reveal whether it was taken."""
        return register_account(
            self.session,
            data,
            ip_address=ip_address,
            issue_verification=self._issue_verification_email,
        )

    def login(self, data: LoginRequest, *, ip_address: str | None = None) -> TokenResponse:
        email = data.email.lower()
        user = self.repo.get_by_email(email)
        # Run verify even when the user is missing to avoid leaking which emails
        # exist via response timing.
        placeholder = "$2b$12$" + "x" * 53
        if not verify_password(data.password, user.password_hash if user else placeholder):
            log_auth_event(
                "login_failure",
                email=email,
                ip_address=ip_address,
                reason="invalid_credentials",
            )
            raise ValidationError("Invalid email or password.")
        if user is None or not user.is_active:
            log_auth_event(
                "login_failure",
                email=email,
                user_id=None if user is None else user.id,
                ip_address=ip_address,
                reason="invalid_credentials",
            )
            raise ValidationError("Invalid email or password.")
        log_auth_event(
            "login_success",
            email=user.email,
            user_id=user.id,
            ip_address=ip_address,
        )
        return self._issue_tokens(user)

    def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except TokenError as exc:
            raise ValidationError(str(exc)) from exc
        user = self.repo.get(int(payload["sub"]))
        if user is None or not user.is_active:
            raise ValidationError("Account is no longer active.")
        if payload.get("ver") != user.token_version:
            raise ValidationError("Session is no longer valid. Please sign in again.")
        self.repo.bump_token_version(user)
        return self._issue_tokens(user)

    def logout(self, refresh_token: str | None, *, ip_address: str | None = None) -> None:
        """Invalidate the refresh session when a valid refresh token is presented."""
        if not refresh_token:
            return
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except TokenError:
            return
        user = self.repo.get(int(payload["sub"]))
        if user is None or not user.is_active:
            return
        if payload.get("ver") != user.token_version:
            return
        self.repo.bump_token_version(user)
        log_auth_event(
            "session_invalidated",
            email=user.email,
            user_id=user.id,
            ip_address=ip_address,
            reason="logout",
        )

    def me(self, user_id: int) -> User:
        user = self.repo.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    def complete_onboarding(self, user_id: int) -> User:
        """Mark the first-run onboarding wizard as finished."""
        user = self.me(user_id)
        if user.onboarding_completed_at is None:
            user.onboarding_completed_at = utcnow()
            self.session.flush()
        return user

    def request_password_reset(
        self,
        data: ForgotPasswordRequest,
        *,
        ip_address: str | None = None,
        schedule_email: Callable[..., Any] | None = None,
    ) -> str:
        """Issue a reset token and email it. Always returns the same message."""
        return issue_password_reset(
            self.session,
            data,
            ip_address=ip_address,
            schedule_email=schedule_email,
        )

    def reset_password(self, data: ResetPasswordRequest, *, ip_address: str | None = None) -> None:
        """Set a new password from a valid reset token."""
        apply_password_reset(self.session, data, ip_address=ip_address)

    def verify_email(self, data: VerifyEmailRequest) -> User:
        """Confirm ownership of an email address from a verification link."""
        token_hash = hash_url_token(data.token)
        now = utcnow()
        row = self.verification_tokens.claim_valid_by_hash(token_hash, now=now)
        if row is None:
            raise ValidationError("Invalid or expired verification link. Request a new one.")
        # Persist the consume before any path that may raise so single-use does
        # not depend on a later delete surviving the request transaction
        # (DAT-18), and so an inactive/missing user cannot leave a replayable
        # link (AUT-30).
        self.session.commit()

        user = self.repo.get(row.user_id)
        if user is None or not user.is_active:
            raise ValidationError("Invalid or expired verification link. Request a new one.")

        if user.email_verified_at is None:
            user.email_verified_at = now
            self.session.flush()
        self.verification_tokens.delete_for_user(user.id)
        return user

    def resend_verification_email(self, user_id: int) -> str:
        """Send a fresh verification link to the signed-in user."""
        user = self.me(user_id)
        if user.email_verified_at is not None:
            raise ValidationError("Email is already verified.")

        self._issue_verification_email(user)
        return _VERIFICATION_SENT_MESSAGE

    def export_data(
        self,
        user_id: int,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> UserDataExport:
        """Return a portable JSON bundle of everything the user owns."""
        return export_user_data(
            self.session,
            self.me(user_id),
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def delete_account(
        self,
        user_id: int,
        data: DeleteAccountRequest,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Permanently remove the signed-in account after password confirmation."""
        delete_user_account(
            self.session,
            self.me(user_id),
            data,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def _issue_verification_email(self, user: User) -> None:
        limit_verification_email_issue(user.email)
        raw_token = generate_password_reset_token()
        expires_at = utcnow() + timedelta(minutes=settings.email_verification_expire_minutes)
        self.verification_tokens.delete_for_user(user.id)
        self.verification_tokens.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=hash_url_token(raw_token),
                expires_at=expires_at,
            )
        )
        verify_url = f"{settings.frontend_base_url.rstrip('/')}/verify-email?token={raw_token}"
        send_verification_email(to_email=user.email, verify_url=verify_url)

    @staticmethod
    def _issue_tokens(user: User) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user.id, version=user.token_version),
            refresh_token=create_refresh_token(user.id, version=user.token_version),
        )
