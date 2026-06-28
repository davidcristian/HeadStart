"""Search request/response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.delivery import DeliveryFailureRead


class SearchBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_id: int
    target_id: int | None = None
    query_url: str = Field(default="", max_length=2000)
    filters: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    interval_seconds: int = Field(default=300, ge=10)
    enabled: bool = True


class SearchCreate(SearchBase):
    pass


class SearchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    target_id: int | None = None
    query_url: str | None = Field(default=None, max_length=2000)
    filters: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    interval_seconds: int | None = Field(default=None, ge=10)
    enabled: bool | None = None


class SearchRead(SearchBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_run_at: datetime | None
    last_error: str | None = None
    next_run_at: datetime
    created_at: datetime
    recent_delivery_failures: list[DeliveryFailureRead] = Field(default_factory=list)


class SearchRunRead(BaseModel):
    """Immediate pipeline result from POST /searches/{id}/run."""

    search_id: int
    found: int = 0
    new: int = 0
    notified: int = 0
    failed: int = 0
    error: str | None = None
