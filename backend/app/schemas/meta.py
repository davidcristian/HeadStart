"""Meta/health schemas."""

from pydantic import BaseModel

from app.schemas.plan import AccountPlanRead


class HealthRead(BaseModel):
    status: str
    version: str
    environment: str


class AdsConfigRead(BaseModel):
    """Optional third-party ad slot for free-tier monetization."""

    external_slot_url: str | None = None


class MetaRead(BaseModel):
    """Capabilities the frontend uses to populate dropdowns."""

    scrapers: list[str]
    notifiers: list[str]
    appliers: list[str]
    mailboxes: list[str]
    inbox_agent_enabled: bool
    plan: AccountPlanRead
    ads: AdsConfigRead


class MessageRead(BaseModel):
    detail: str
