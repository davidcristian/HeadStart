"""User: an account that owns its own sources, searches, targets, and creds."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.application_artifact import ApplicationArtifact
    from app.models.application_profile import ApplicationProfile
    from app.models.email_verification_token import EmailVerificationToken
    from app.models.inbox_classification import InboxClassification
    from app.models.inbox_pending_reply import InboxPendingReply
    from app.models.inbox_poll_state import InboxPollState
    from app.models.inbox_reply_draft import InboxReplyDraft
    from app.models.inbox_reply_send_log import InboxReplySendLog
    from app.models.mailbox_credential import MailboxCredential
    from app.models.notification_target import NotificationTarget
    from app.models.password_reset_token import PasswordResetToken
    from app.models.promo_redemption import PromoRedemption
    from app.models.promo_validation_attempt import PromoValidationAttempt
    from app.models.search import Search
    from app.models.site_credential import SiteCredential
    from app.models.source import Source


class User(Base, TimestampMixin):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # The first registered user becomes admin (see AuthService.register).
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Incremented to invalidate previously issued RSS feed URLs.
    feed_token_version: Mapped[int] = mapped_column(default=0, nullable=False)
    # Incremented to invalidate previously issued access/refresh tokens
    # (e.g. on password reset), so credential rotation terminates active sessions.
    token_version: Mapped[int] = mapped_column(default=0, nullable=False)
    # Set when the first-run onboarding wizard is finished (or skipped).
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set when the user confirms ownership of their email address.
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Subscription tier (Stripe webhooks or admin panel).
    plan: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Unix `created` of the last applied Stripe subscription lifecycle event
    # (updated/deleted). Stale/out-of-order webhooks older than this are ignored.
    stripe_billing_event_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Optional override for SUMMARY_PROVIDER; null uses the server default.
    summary_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Fernet-encrypted API key for the selected hosted provider (openai/gemini/anthropic).
    summary_api_key_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional per-purpose provider overrides (cover_letter, resume_curation, ...).
    ai_purpose_providers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Optional per-purpose model overrides keyed by purpose id.
    ai_purpose_models: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Preferred notification/auth email locale (`en` / `de`); null → DEFAULT_LOCALE (NTF-12).
    locale: Mapped[str | None] = mapped_column(String(16), nullable=True)

    sources: Mapped[list["Source"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    searches: Mapped[list["Search"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    targets: Mapped[list["NotificationTarget"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    credentials: Mapped[list["SiteCredential"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    email_verification_tokens: Mapped[list["EmailVerificationToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    application_profile: Mapped["ApplicationProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    mailbox_credential: Mapped["MailboxCredential | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    inbox_classifications: Mapped[list["InboxClassification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    inbox_poll_state: Mapped["InboxPollState | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    inbox_reply_drafts: Mapped[list["InboxReplyDraft"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    inbox_pending_replies: Mapped[list["InboxPendingReply"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    inbox_reply_send_logs: Mapped[list["InboxReplySendLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    # DB FK already ON DELETE CASCADE; ORM cascade keeps SQLite/test erasure
    # aligned when foreign_keys are off and matches the other owned collections.
    application_artifacts: Mapped[list["ApplicationArtifact"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    promo_redemptions: Mapped[list["PromoRedemption"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    promo_validation_attempts: Mapped[list["PromoValidationAttempt"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
