"""Shared apply-adapter data types."""

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.profile import ProfileData


class ApplyContext(BaseModel):
    """Everything an applier needs to submit (or preview) one application."""

    job_external_id: str
    job_title: str
    company: str
    job_url: str
    config: dict[str, Any] = Field(default_factory=dict)
    profile: ProfileData
    credentials: dict[str, dict[str, str]] | None = None
    dry_run: bool = False


class ApplyResult(BaseModel):
    """Outcome of a single apply attempt."""

    status: str  # "submitted" | "dry_run" | "failed"
    error: str | None = None
    payload: dict[str, Any] | None = None
    external_application_id: str | None = None
