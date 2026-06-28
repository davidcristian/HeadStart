"""Meta/health schemas."""

from pydantic import BaseModel


class HealthRead(BaseModel):
    status: str
    version: str
    environment: str


class MetaRead(BaseModel):
    """Capabilities the frontend uses to populate dropdowns."""

    scrapers: list[str]
    notifiers: list[str]


class MessageRead(BaseModel):
    detail: str
