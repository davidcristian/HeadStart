"""Curated portal catalog schemas."""

from typing import Any, Literal

from pydantic import BaseModel, Field

PortalCategory = Literal["big_tech", "unicorn", "ai"]


class PortalRead(BaseModel):
    """A curated employer portal the user can add as a source."""

    id: str
    company_name: str
    category: PortalCategory
    adapter_key: str
    base_url: str
    default_config: dict[str, Any] = Field(default_factory=dict)
    supports_auto_apply: bool
    allowed_on_plan: bool
    already_added: bool


class PortalListRead(BaseModel):
    """Catalog listing with optional filters applied."""

    items: list[PortalRead]
    categories: list[PortalCategory]
