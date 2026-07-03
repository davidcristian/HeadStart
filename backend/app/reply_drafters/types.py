"""Reply draft input and output types."""

from pydantic import BaseModel

from app.email_classifiers.types import LinkedApplicationContext
from app.schemas.profile import ProfileData


class ReplyDraftContext(BaseModel):
    """Inbound recruiter email plus candidate profile for drafting a reply."""

    inbound_subject: str = ""
    inbound_from: str = ""
    inbound_body: str = ""
    classification_label: str = ""
    linked_application: LinkedApplicationContext | None = None
    profile: ProfileData
    mailbox_user_email: str = ""


class ReplyDraftResult(BaseModel):
    """Drafter output before persistence."""

    subject: str = ""
    body: str = ""
    notes: str = ""
