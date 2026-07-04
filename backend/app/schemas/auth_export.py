"""GDPR data-export DTOs for user-owned rows beyond the core account bundle."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApplicationArtifactExport(BaseModel):
    """Generated document with decrypted bytes (base64) for portability."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    artifact_type: str
    filename: str
    content_type: str
    size_bytes: int = Field(ge=0)
    content_sha256: str
    created_at: datetime
    data_b64: str


class DeliveryLogExport(BaseModel):
    """Notification delivery attempt owned via the user's searches."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    seen_job_id: int
    target_id: int | None = None
    status: str
    error: str | None = None
    sent_at: datetime


class MailboxCredentialExport(BaseModel):
    """Mailbox connection metadata with secrets redacted."""

    id: int
    connector_type: str
    enabled: bool
    created_at: datetime
    config: dict[str, object]


class InboxClassificationExport(BaseModel):
    """Persisted inbox classification row for the account owner."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    seen_job_id: int | None = None
    message_uid: int
    message_id: str | None = None
    label: str
    confidence: float
    reason: str
    provider: str
    fallback: bool
    subject: str
    from_addr: str
    payload: dict[str, Any] | None = None
    routed_to: str | None = None
    routing_status: str | None = None
    routing_error: str | None = None
    created_at: datetime


class InboxReplyDraftExport(BaseModel):
    """Stored recruiter reply draft for the account owner."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    inbox_classification_id: int
    seen_job_id: int | None = None
    message_uid: int
    subject: str
    body_text: str
    provider: str
    fallback: bool
    status: str
    payload: dict[str, Any] | None = None
    created_at: datetime


class InboxPendingReplyExport(BaseModel):
    """Delayed auto-reply queue row for the account owner."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    inbox_reply_draft_id: int
    send_after: datetime
    status: str
    sent_at: datetime | None = None
    error: str | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime


class InboxReplySendLogExport(BaseModel):
    """Auto-reply send audit row for the account owner."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    inbox_reply_draft_id: int
    inbox_pending_reply_id: int | None = None
    outcome: str
    reason: str
    subject: str
    body_excerpt: str
    payload: dict[str, Any] | None = None
    created_at: datetime


class ProfileFileExport(BaseModel):
    """Uploaded resume or LaTeX template bytes for portability."""

    filename: str
    content_type: str | None = None
    data_b64: str
    format: str | None = None
    entrypoint: str | None = None
    file_count: int | None = None
