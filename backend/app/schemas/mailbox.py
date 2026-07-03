"""Mailbox credential request/response schemas.

Passwords are accepted on write but NEVER returned on read.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.inbox.types import MailboxConfig


class MailboxCredentialUpsert(BaseModel):
    connector_type: str = Field(default="imap_smtp", max_length=32)
    enabled: bool = True
    config: MailboxConfig


class MailboxCredentialUpdate(BaseModel):
    enabled: bool | None = None
    config: MailboxConfig | None = None


class MailboxCredentialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    connector_type: str
    enabled: bool
    created_at: datetime
    has_config: bool = True
    imap_host: str | None = None
    smtp_host: str | None = None
    imap_user: str | None = None


class MailboxTestRequest(BaseModel):
    """Optional inline config; when omitted the saved credential or env fallback is used."""

    config: MailboxConfig | None = None


class MailboxTestResponse(BaseModel):
    imap_ok: bool
    smtp_ok: bool
    error: str | None = None
