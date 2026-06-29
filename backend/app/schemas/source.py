"""Source request/response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    adapter_key: str = Field(min_length=1, max_length=100)
    base_url: str = Field(default="", max_length=1000)
    default_config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    adapter_key: str | None = Field(default=None, min_length=1, max_length=100)
    base_url: str | None = Field(default=None, max_length=1000)
    default_config: dict[str, Any] | None = None
    enabled: bool | None = None


class SourceRead(SourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class JobPostingPreview(BaseModel):
    """A single scraped posting returned by a dry-run source test."""

    external_id: str
    title: str
    company: str
    location: str = ""
    url: str


class SourceTestRequest(BaseModel):
    """Optional scrape overrides for POST /sources/{id}/test."""

    query_url: str | None = Field(default=None, max_length=2000)
    filters: dict[str, Any] | None = None
    config: dict[str, Any] | None = None


class SourceTestResult(BaseModel):
    """Dry-run scrape result; nothing is persisted or notified."""

    ok: bool
    found: int = 0
    sample: list[JobPostingPreview] = Field(default_factory=list)
    error: str | None = None


class SourceDetectRequest(BaseModel):
    """Input for POST /sources/detect (browser extension and UI helpers)."""

    url: str = Field(min_length=1, max_length=2000)
    page_title: str | None = Field(default=None, max_length=500)


class SourceDetectResult(BaseModel):
    """Suggested source fields inferred from a careers-page URL."""

    adapter_key: str
    suggested_name: str
    base_url: str
    default_config: dict[str, Any] = Field(default_factory=dict)
    query_url: str
