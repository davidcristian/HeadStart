"""Authentication business logic: registration, login, token refresh."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = UserRepository(session)

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

    @staticmethod
    def _issue_tokens(user: User) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )
