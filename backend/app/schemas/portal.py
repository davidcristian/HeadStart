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


class PortalSearchRequest(BaseModel):
    """Cross-portal job search (Pro+)."""

    keywords: str = Field(min_length=1, max_length=200)
    category: PortalCategory | None = None
    portal_ids: list[str] | None = Field(default=None, max_length=30)
    location: str | None = Field(default=None, max_length=200)
    workplace: Literal["remote", "hybrid", "onsite"] | None = None


class PortalJobRead(BaseModel):
    """A job posting from a curated portal search result."""

    portal_id: str
    company_name: str
    external_id: str
    title: str
    location: str = ""
    url: str = ""


class PortalSearchErrorRead(BaseModel):
    """Per-portal scrape failure during a cross-portal search."""

    portal_id: str
    company_name: str
    error: str


class PortalSearchResultRead(BaseModel):
    """Aggregated matches across curated portals."""

    items: list[PortalJobRead]
    portals_searched: int
    portals_failed: int
    errors: list[PortalSearchErrorRead] = Field(default_factory=list)


class PortalSubscribeRequest(BaseModel):
    """Create sources and searches for curated portals in one step."""

    portal_ids: list[str] = Field(min_length=1, max_length=30)
    keywords: str = Field(min_length=1, max_length=200)
    target_id: int
    interval_seconds: int = Field(default=900, ge=10)
    notification_mode: Literal["immediate", "digest"] = "immediate"
    digest_interval_seconds: int = Field(default=3600, ge=60)
    location: str | None = Field(default=None, max_length=200)
    workplace: Literal["remote", "hybrid", "onsite"] | None = None


class PortalSubscribeResultRead(BaseModel):
    """Outcome of bulk alert setup from curated portals."""

    sources_created: int
    searches_created: int
    search_ids: list[int]
    skipped_portal_ids: list[str] = Field(default_factory=list)
    message: str | None = None
