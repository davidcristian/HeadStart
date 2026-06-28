"""Auth endpoints: register, login, refresh, password reset, and current-user."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import (
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


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)) -> UserRead:
    """Create an account. The first registered user becomes the admin."""
    return UserRead.model_validate(AuthService(db).register(data))


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return AuthService(db).login(data)


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return AuthService(db).refresh(data.refresh_token)


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
