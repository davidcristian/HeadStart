"""Application log response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApplicationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    seen_job_id: int
    job_title: str
    job_company: str
    job_url: str
    status: str
    dry_run: bool
    error: str | None = None
    payload: dict[str, Any] | None = None
    external_application_id: str | None = None
    created_at: datetime


class ApplicationLogListParams(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)
