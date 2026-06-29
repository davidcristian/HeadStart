"""Auth request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    # Optional: the refresh token normally arrives via the httpOnly cookie. The
    # body field is kept for non-browser clients that manage tokens themselves.
    refresh_token: str | None = Field(default=None, min_length=1)


class TokenResponse(BaseModel):
    """Internal token pair returned by the auth service."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    """API response body: only the access token. The refresh token is set as an
    httpOnly cookie and never exposed to JavaScript."""

    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_admin: bool
    is_active: bool
    created_at: datetime


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str
