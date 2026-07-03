"""Shared inbox / mailbox connector data types."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GmailMailboxConfig(BaseModel):
    """OAuth tokens for the Gmail API connector."""

    email_address: str = Field(min_length=3, max_length=320)
    access_token: str = Field(min_length=1, max_length=4096)
    refresh_token: str = Field(min_length=1, max_length=4096)
    token_expiry: str | None = None


class MailboxConfig(BaseModel):
    """IMAP + SMTP connection settings for the imap_smtp connector."""

    imap_host: str = Field(min_length=1, max_length=255)
    imap_port: int = Field(default=993, ge=1, le=65535)
    imap_use_ssl: bool = True
    imap_user: str = Field(min_length=1, max_length=320)
    imap_password: str = Field(min_length=1, max_length=512)
    imap_mailbox: str = Field(default="INBOX", min_length=1, max_length=255)
    smtp_host: str = Field(min_length=1, max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_use_tls: bool = True
    smtp_user: str = Field(default="", max_length=320)
    smtp_password: str = Field(default="", max_length=512)
    smtp_from: str = Field(default="", max_length=320)


class MailboxContext(BaseModel):
    """Everything a mailbox connector needs for one user session."""

    connector_type: str
    config: MailboxConfig | GmailMailboxConfig
    user_id: int | None = None


class InboxMessage(BaseModel):
    """Normalized inbound email for triage and classification."""

    uid: int
    message_id: str | None = None
    in_reply_to: str | None = None
    references: str | None = None
    from_addr: str = ""
    to_addrs: list[str] = Field(default_factory=list)
    subject: str = ""
    body_text: str = ""
    received_at: datetime | None = None
    raw_headers: dict[str, str] = Field(default_factory=dict)


class OutboundMessage(BaseModel):
    """Plain-text outbound email."""

    to: list[str] = Field(min_length=1)
    subject: str = Field(min_length=1, max_length=998)
    body: str = Field(min_length=1)
    in_reply_to: str | None = None
    references: str | None = None
    extra_headers: dict[str, str] = Field(default_factory=dict)


class FetchResult(BaseModel):
    """Outcome of a mailbox fetch pass."""

    messages: list[InboxMessage] = Field(default_factory=list)
    max_uid: int | None = None


class SendResult(BaseModel):
    """Outcome of a single outbound send."""

    status: str  # "sent" | "failed"
    error: str | None = None


class ConnectionTestResult(BaseModel):
    """Outcome of validating IMAP + SMTP connectivity."""

    imap_ok: bool
    smtp_ok: bool
    error: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class MoveResult(BaseModel):
    """Outcome of moving one message to another IMAP mailbox folder."""

    status: str  # "moved" | "skipped" | "failed"
    destination: str | None = None
    error: str | None = None
