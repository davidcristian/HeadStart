"""Email classification input and output types."""

from pydantic import BaseModel, Field

from app.inbox.types import InboxMessage


class LinkedApplicationContext(BaseModel):
    """Known application context for classifying one inbound email."""

    seen_job_id: int
    job_title: str = ""
    company: str = ""
    employer_domain: str = ""


class EmailClassifyContext(BaseModel):
    """Sanitized email plus optional linked application metadata."""

    message: InboxMessage
    linked_application: LinkedApplicationContext | None = None
    mailbox_user_email: str = ""


class EmailClassificationResult(BaseModel):
    """Classifier output before persistence."""

    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""
