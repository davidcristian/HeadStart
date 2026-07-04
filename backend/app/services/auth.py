"""Authentication business logic: registration, login, token refresh, password reset."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import send_password_reset_email, send_verification_email
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_password_reset_token,
    hash_password,
    hash_password_reset_token,
    verify_password,
)
from app.models.base import utcnow
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_reset_token import PasswordResetToken
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

_PASSWORD_RESET_SENT_MESSAGE = (
    "If an account exists for that email, a password reset link has been sent."
)
_VERIFICATION_SENT_MESSAGE = (
    "If your account is not yet verified, a verification link has been sent."
)


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = UserRepository(session)
        self.reset_tokens = PasswordResetTokenRepository(session)
        self.verification_tokens = EmailVerificationTokenRepository(session)

    def register(self, data: RegisterRequest) -> User:
        """Create an account. The very first user becomes the admin."""
        email = data.email.lower()
        if self.repo.get_by_email(email) is not None:
            raise ConflictError("An account with this email already exists.")
        user = User(
            email=email,
            password_hash=hash_password(data.password),
            is_admin=False,
            is_active=True,
        )
        user = self.repo.add(user)
        if self.repo.claim_bootstrap_admin(user.id):
            user.is_admin = True
            self.session.flush()
        self._issue_verification_email(user)
        return user

    def login(self, data: LoginRequest) -> TokenResponse:
        user = self.repo.get_by_email(data.email.lower())
        # Run verify even when the user is missing to avoid leaking which emails
        # exist via response timing.
        placeholder = "$2b$12$" + "x" * 53
        if not verify_password(data.password, user.password_hash if user else placeholder):
            raise ValidationError("Invalid email or password.")
        if user is None or not user.is_active:
            raise ValidationError("Invalid email or password.")
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

    def logout(self, refresh_token: str | None) -> None:
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

    def request_password_reset(self, data: ForgotPasswordRequest) -> str:
        """Issue a reset token and email it. Always returns the same message."""
        user = self.repo.get_by_email(data.email.lower())
        if user is None or not user.is_active:
            return _PASSWORD_RESET_SENT_MESSAGE

        raw_token = generate_password_reset_token()
        expires_at = utcnow() + timedelta(minutes=settings.password_reset_expire_minutes)
        self.reset_tokens.delete_for_user(user.id)
        self.reset_tokens.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_password_reset_token(raw_token),
                expires_at=expires_at,
            )
        )

        reset_url = f"{settings.frontend_base_url.rstrip('/')}/reset-password?token={raw_token}"
        send_password_reset_email(to_email=user.email, reset_url=reset_url)
        return _PASSWORD_RESET_SENT_MESSAGE

    def reset_password(self, data: ResetPasswordRequest) -> None:
        """Set a new password from a valid reset token."""
        token_hash = hash_password_reset_token(data.token)
        now = utcnow()
        row = self.reset_tokens.get_valid_by_hash(token_hash, now=now)
        if row is None:
            raise ValidationError("Invalid or expired reset link. Request a new one.")

        user = self.repo.get(row.user_id)
        if user is None or not user.is_active:
            raise ValidationError("Invalid or expired reset link. Request a new one.")

        self.repo.update_password(user, hash_password(data.password))
        # Terminate sessions that may have been opened with a compromised
        # credential: bump the token version so outstanding access/refresh
        # tokens (which carry the old `ver`) stop validating.
        self.repo.bump_token_version(user)
        self.repo.bump_feed_token_version(user)
        self.reset_tokens.delete_for_user(user.id)

    def verify_email(self, data: VerifyEmailRequest) -> User:
        """Confirm ownership of an email address from a verification link."""
        token_hash = hash_password_reset_token(data.token)
        now = utcnow()
        row = self.verification_tokens.get_valid_by_hash(token_hash, now=now)
        if row is None:
            raise ValidationError("Invalid or expired verification link. Request a new one.")

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
        raw_token = generate_password_reset_token()
        expires_at = utcnow() + timedelta(minutes=settings.email_verification_expire_minutes)
        self.verification_tokens.delete_for_user(user.id)
        self.verification_tokens.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=hash_password_reset_token(raw_token),
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
