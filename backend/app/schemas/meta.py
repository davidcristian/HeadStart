"""Meta/health schemas."""

from pydantic import BaseModel

from app.schemas.plan import AccountPlanRead


class HealthRead(BaseModel):
    status: str
    version: str
    environment: str


class MetaRead(BaseModel):
    """Capabilities the frontend uses to populate dropdowns."""

    scrapers: list[str]
    notifiers: list[str]
    appliers: list[str]
    plan: AccountPlanRead


class MessageRead(BaseModel):
    detail: str
