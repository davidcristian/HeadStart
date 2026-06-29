"""Auth endpoints: register, login, refresh, logout, password reset, current-user."""

from fastapi import APIRouter, Cookie, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserRead,
)
from app.services.auth import AuthService

router = APIRouter()


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Store the refresh token in an httpOnly cookie scoped to the auth routes."""
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,  # type: ignore[arg-type]
        path=settings.auth_cookie_path,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path=settings.auth_cookie_path,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,  # type: ignore[arg-type]
    )


def _issue(response: Response, tokens: TokenResponse) -> AccessTokenResponse:
    """Set the refresh cookie and return only the access token to the caller."""
    _set_refresh_cookie(response, tokens.refresh_token)
    return AccessTokenResponse(access_token=tokens.access_token)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)) -> UserRead:
    """Create an account. The first registered user becomes the admin."""
    return UserRead.model_validate(AuthService(db).register(data))


@router.post("/login", response_model=AccessTokenResponse)
def login(
    data: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> AccessTokenResponse:
    return _issue(response, AuthService(db).login(data))


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    response: Response,
    data: RefreshRequest | None = None,
    refresh_cookie: str | None = Cookie(default=None, alias=settings.auth_cookie_name),
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    """Exchange a refresh token (httpOnly cookie, or body for API clients) for a
    fresh access token, rotating the refresh cookie."""
    token = refresh_cookie or (data.refresh_token if data else None)
    if not token:
        raise ValidationError("Missing refresh token.")
    return _issue(response, AuthService(db).refresh(token))


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response) -> MessageResponse:
    """Clear the refresh cookie. Safe to call without an active session."""
    _clear_refresh_cookie(response)
    return MessageResponse(message="Logged out.")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """Request a password-reset email. Response is identical whether the email exists."""
    message = AuthService(db).request_password_reset(data)
    return MessageResponse(message=message)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """Set a new password using a token from the reset email."""
    AuthService(db).reset_password(data)
    return MessageResponse(message="Password updated. You can sign in with your new password.")


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user)
