"""Shared inbox / mailbox connector data types."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Bounds for client-supplied and normalized inbound mail (INB-14).
# Subject matches OutboundMessage / RFC 5322 line length; body caps multi-MB
# classify payloads while still fitting typical recruiter threads.
INBOX_MESSAGE_ID_MAX_LENGTH = 998
INBOX_SUBJECT_MAX_LENGTH = 998
INBOX_ADDR_MAX_LENGTH = 320
INBOX_BODY_MAX_LENGTH = 100_000
INBOX_REFERENCES_MAX_LENGTH = 8_192
INBOX_TO_ADDRS_MAX_ITEMS = 50
INBOX_RAW_HEADERS_MAX_ITEMS = 64
INBOX_HEADER_NAME_MAX_LENGTH = 256
INBOX_HEADER_VALUE_MAX_LENGTH = 8_192


def clip_inbox_str(value: str | None, max_length: int) -> str | None:
    """Truncate optional strings so mailbox parsers stay within InboxMessage bounds."""
    if value is None:
        return None
    if len(value) <= max_length:
        return value
    return value[:max_length]


def clip_inbox_headers(headers: dict[str, str]) -> dict[str, str]:
    """Keep header maps within InboxMessage item and value caps."""
    clipped: dict[str, str] = {}
    for key, value in headers.items():
        if len(clipped) >= INBOX_RAW_HEADERS_MAX_ITEMS:
            break
        name = (
            key if len(key) <= INBOX_HEADER_NAME_MAX_LENGTH else key[:INBOX_HEADER_NAME_MAX_LENGTH]
        )
        clipped[name] = (
            value
            if len(value) <= INBOX_HEADER_VALUE_MAX_LENGTH
            else value[:INBOX_HEADER_VALUE_MAX_LENGTH]
        )
    return clipped


class GmailMailboxConfig(BaseModel):
    """OAuth tokens for the Gmail API connector."""

    email_address: str = Field(min_length=3, max_length=320)
    access_token: str = Field(min_length=1, max_length=4096)
    refresh_token: str = Field(min_length=1, max_length=4096)
    token_expiry: str | None = None


class OutlookMailboxConfig(BaseModel):
    """OAuth tokens for the Microsoft Graph mailbox connector."""

    email_address: str = Field(min_length=3, max_length=320)
    access_token: str = Field(min_length=1, max_length=4096)
    refresh_token: str = Field(min_length=1, max_length=4096)
    token_expiry: str | None = None


class YahooMailboxConfig(BaseModel):
    """OAuth tokens for the Yahoo Mail IMAP/SMTP connector."""

    email_address: str = Field(min_length=3, max_length=320)
    access_token: str = Field(min_length=1, max_length=4096)
    refresh_token: str = Field(min_length=1, max_length=4096)
    token_expiry: str | None = None


class FastmailMailboxConfig(BaseModel):
    """API token auth for the Fastmail JMAP connector."""

    email_address: str = Field(min_length=3, max_length=320)
    api_token: str = Field(min_length=1, max_length=4096)


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
    config: (
        MailboxConfig
        | GmailMailboxConfig
        | OutlookMailboxConfig
        | YahooMailboxConfig
        | FastmailMailboxConfig
    )
    user_id: int | None = None


class InboxMessage(BaseModel):
    """Normalized inbound email for triage and classification."""

    uid: int
    message_id: str | None = Field(default=None, max_length=INBOX_MESSAGE_ID_MAX_LENGTH)
    in_reply_to: str | None = Field(default=None, max_length=INBOX_MESSAGE_ID_MAX_LENGTH)
    references: str | None = Field(default=None, max_length=INBOX_REFERENCES_MAX_LENGTH)
    from_addr: str = Field(default="", max_length=INBOX_ADDR_MAX_LENGTH)
    to_addrs: list[str] = Field(default_factory=list, max_length=INBOX_TO_ADDRS_MAX_ITEMS)
    subject: str = Field(default="", max_length=INBOX_SUBJECT_MAX_LENGTH)
    body_text: str = Field(default="", max_length=INBOX_BODY_MAX_LENGTH)
    received_at: datetime | None = None
    raw_headers: dict[str, str] = Field(
        default_factory=dict, max_length=INBOX_RAW_HEADERS_MAX_ITEMS
    )

    @field_validator("to_addrs")
    @classmethod
    def validate_to_addrs(cls, value: list[str]) -> list[str]:
        """Reject overlong recipient addresses on the classify API path."""
        for addr in value:
            if len(addr) > INBOX_ADDR_MAX_LENGTH:
                raise ValueError(
                    f"each to_addrs entry cannot exceed {INBOX_ADDR_MAX_LENGTH} characters"
                )
        return value

    @field_validator("raw_headers")
    @classmethod
    def validate_raw_headers(cls, value: dict[str, str]) -> dict[str, str]:
        """Reject overlong header names/values on the classify API path."""
        for key, header_value in value.items():
            if len(key) > INBOX_HEADER_NAME_MAX_LENGTH:
                raise ValueError(
                    f"each raw_headers key cannot exceed {INBOX_HEADER_NAME_MAX_LENGTH} characters"
                )
            if len(header_value) > INBOX_HEADER_VALUE_MAX_LENGTH:
                raise ValueError(
                    "each raw_headers value cannot exceed "
                    f"{INBOX_HEADER_VALUE_MAX_LENGTH} characters"
                )
        return value


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
