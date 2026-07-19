"""Auth request/response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.application_log import ApplicationLogRead
from app.schemas.auth_export import (
    ApplicationArtifactExport,
    DeliveryLogExport,
    InboxClassificationExport,
    InboxPendingReplyExport,
    InboxReplyDraftExport,
    InboxReplySendLogExport,
    MailboxCredentialExport,
    ProfileFileExport,
)
from app.schemas.job import JobRead
from app.schemas.profile import ProfileRead
from app.schemas.promo import PromoRedemptionRead
from app.schemas.search import SearchRead
from app.schemas.source import SourceRead
from app.schemas.target import TargetRead


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
    plan: Literal["free", "starter", "plus", "pro"] = "free"
    onboarding_completed_at: datetime | None = None
    email_verified_at: datetime | None = None
    # Null means inherit Settings.default_locale for notifier/auth copy (NTF-12).
    locale: Literal["en", "de"] | None = None
    created_at: datetime


class UpdateMeRequest(BaseModel):
    """Self-service account fields the signed-in user may change."""

    locale: Literal["en", "de"] | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1)


class MessageResponse(BaseModel):
    message: str


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class CredentialExport(BaseModel):
    """Site credential with decrypted secrets — only returned in a data export."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    name: str
    enabled: bool
    created_at: datetime
    cookies: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    session: dict[str, str] = Field(default_factory=dict)


class UserDataExport(BaseModel):
    """Machine-readable bundle of everything the signed-in user owns."""

    exported_at: datetime
    format_version: int = 2
    account: UserRead
    sources: list[SourceRead]
    searches: list[SearchRead]
    targets: list[TargetRead]
    credentials: list[CredentialExport]
    profile: ProfileRead | None = None
    resume_file: ProfileFileExport | None = None
    resume_template: ProfileFileExport | None = None
    jobs: list[JobRead]
    applications: list[ApplicationLogRead] = Field(default_factory=list)
    artifacts: list[ApplicationArtifactExport] = Field(default_factory=list)
    deliveries: list[DeliveryLogExport] = Field(default_factory=list)
    mailbox: MailboxCredentialExport | None = None
    inbox_classifications: list[InboxClassificationExport] = Field(default_factory=list)
    inbox_reply_drafts: list[InboxReplyDraftExport] = Field(default_factory=list)
    inbox_pending_replies: list[InboxPendingReplyExport] = Field(default_factory=list)
    inbox_reply_send_logs: list[InboxReplySendLogExport] = Field(default_factory=list)
    promo_redemptions: list[PromoRedemptionRead] = Field(default_factory=list)
