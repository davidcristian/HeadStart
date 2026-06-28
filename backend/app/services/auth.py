"""Authentication business logic: registration, login, token refresh, password reset."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import send_password_reset_email
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
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.repositories.password_reset_tokens import PasswordResetTokenRepository
from app.repositories.users import UserRepository
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)

_PASSWORD_RESET_SENT_MESSAGE = (
    "If an account exists for that email, a password reset link has been sent."
)


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = UserRepository(session)
        self.reset_tokens = PasswordResetTokenRepository(session)

    def register(self, data: RegisterRequest) -> User:
        """Create an account. The very first user becomes the admin."""
        email = data.email.lower()
        if self.repo.get_by_email(email) is not None:
            raise ConflictError("An account with this email already exists.")
        is_first = self.repo.count() == 0
        user = User(
            email=email,
            password_hash=hash_password(data.password),
            is_admin=is_first,
            is_active=True,
        )
        return self.repo.add(user)

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
        return self._issue_tokens(user)

    def me(self, user_id: int) -> User:
        user = self.repo.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")
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
        self.reset_tokens.delete_for_user(user.id)

    @staticmethod
    def _issue_tokens(user: User) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )
