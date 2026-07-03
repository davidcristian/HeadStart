"""API schemas for inbox reply drafts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReplyDraftRequest(BaseModel):
    """Draft a reply for one classified inbound message."""

    classification_id: int | None = Field(default=None, ge=1)
    message_uid: int | None = Field(default=None, ge=1)
    regenerate: bool = False

    @model_validator(mode="after")
    def require_classification_or_uid(self) -> "ReplyDraftRequest":
        if self.classification_id is None and self.message_uid is None:
            raise ValueError("Provide either classification_id or message_uid")
        return self


class ReplyDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    classification_id: int
    seen_job_id: int | None = None
    message_uid: int
    subject: str
    body_text: str
    provider: str
    fallback: bool
    status: str
    notes: str = ""
    queue_status: str | None = None
    send_after: datetime | None = None
    created_at: datetime


class ReplyDraftListParams(BaseModel):
    seen_job_id: int | None = Field(default=None, ge=1)
    limit: int = Field(default=50, ge=1, le=200)


class ReplyDraftSummary(BaseModel):
    """Compact reply draft for the application pipeline view."""

    id: int
    classification_id: int
    subject: str
    body_text: str
    provider: str
    created_at: datetime
