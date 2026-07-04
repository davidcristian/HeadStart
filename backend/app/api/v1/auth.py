"""Auth endpoints: register, login, refresh, logout, password reset, current-user."""

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_verified_user
from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.rate_limit import (
    limit_forgot_password,
    limit_login,
    limit_refresh,
    limit_register,
    limit_resend_verification,
    limit_token_guess,
)
from app.core.request_meta import request_meta
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserDataExport,
    UserRead,
    VerifyEmailRequest,
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
def register(data: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> UserRead:
    """Create an account. The first registered user becomes the admin."""
    limit_register(request)
    return UserRead.model_validate(AuthService(db).register(data))


@router.post("/login", response_model=AccessTokenResponse)
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    limit_login(request, data.email)
    meta = request_meta(request)
    return _issue(response, AuthService(db).login(data, ip_address=meta.ip_address))


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    request: Request,
    response: Response,
    data: RefreshRequest | None = None,
    refresh_cookie: str | None = Cookie(default=None, alias=settings.auth_cookie_name),
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    """Exchange a refresh token (httpOnly cookie, or body for API clients) for a
    fresh access token, rotating the refresh cookie."""
    limit_refresh(request)
    token = refresh_cookie or (data.refresh_token if data else None)
    if not token:
        raise ValidationError("Missing refresh token.")
    return _issue(response, AuthService(db).refresh(token))


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    refresh_cookie: str | None = Cookie(default=None, alias=settings.auth_cookie_name),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Clear the refresh cookie and revoke the server-side refresh session."""
    meta = request_meta(request)
    AuthService(db).logout(refresh_cookie, ip_address=meta.ip_address)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Logged out.")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    data: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)
) -> MessageResponse:
    """Request a password-reset email. Response is identical whether the email exists."""
    limit_forgot_password(request, data.email)
    meta = request_meta(request)
    message = AuthService(db).request_password_reset(data, ip_address=meta.ip_address)
    return MessageResponse(message=message)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    data: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)
) -> MessageResponse:
    """Set a new password using a token from the reset email."""
    limit_token_guess(request, kind="reset")
    meta = request_meta(request)
    AuthService(db).reset_password(data, ip_address=meta.ip_address)
    return MessageResponse(message="Password updated. You can sign in with your new password.")


@router.post("/verify-email", response_model=UserRead)
def verify_email(
    data: VerifyEmailRequest, request: Request, db: Session = Depends(get_db)
) -> UserRead:
    """Confirm an email address using a token from the verification email."""
    limit_token_guess(request, kind="verify")
    return UserRead.model_validate(AuthService(db).verify_email(data))


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> MessageResponse:
    """Send another verification email to the signed-in user."""
    limit_resend_verification(user.id)
    message = AuthService(db).resend_verification_email(user.id)
    return MessageResponse(message=message)


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user)


@router.post("/me/complete-onboarding", response_model=UserRead)
def complete_onboarding(
    user: User = Depends(get_verified_user), db: Session = Depends(get_db)
) -> UserRead:
    """Mark the first-run onboarding wizard as finished."""
    return UserRead.model_validate(AuthService(db).complete_onboarding(user.id))


@router.get("/me/export", response_model=UserDataExport)
def export_my_data(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserDataExport:
    """Download a JSON bundle of all data owned by the signed-in account."""
    meta = request_meta(request)
    return AuthService(db).export_data(
        user.id,
        ip_address=meta.ip_address,
        user_agent=meta.user_agent,
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(
    data: DeleteAccountRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Permanently delete the signed-in account after password confirmation."""
    meta = request_meta(request)
    AuthService(db).delete_account(
        user.id,
        data,
        ip_address=meta.ip_address,
        user_agent=meta.user_agent,
    )
    _clear_refresh_cookie(response)
