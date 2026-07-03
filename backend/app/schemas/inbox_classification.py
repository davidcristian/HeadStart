"""API schemas for inbox email classification."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.inbox.types import InboxMessage

EmailClassificationLabelRead = Literal[
    "general",
    "rejection",
    "follow_up",
    "interview_request",
    "self_ghost_archive",
    "out_of_scope",
]


class EmailClassifyRequest(BaseModel):
    """Classify one inbound message by body or mailbox UID."""

    message: InboxMessage | None = None
    uid: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_message_or_uid(self) -> "EmailClassifyRequest":
        if self.message is None and self.uid is None:
            raise ValueError("Provide either message or uid")
        return self


class LinkedApplicationRead(BaseModel):
    seen_job_id: int
    job_title: str = ""
    company: str = ""


class EmailClassificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_uid: int
    message_id: str | None = None
    label: EmailClassificationLabelRead
    confidence: float
    reason: str
    provider: str
    fallback: bool
    subject: str
    from_addr: str
    linked_application: LinkedApplicationRead | None = None
    created_at: datetime


class EmailClassificationListParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
