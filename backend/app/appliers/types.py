"""Shared apply-adapter data types."""

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.profile import ProfileData, ResumeFile


class ApplyContext(BaseModel):
    """Everything an applier needs to submit (or preview) one application.

    ``dry_run`` defaults to True so a caller that omits the flag cannot
    accidentally POST a live application; pass ``dry_run=False`` explicitly.
    """

    job_external_id: str
    job_title: str
    company: str
    job_url: str
    config: dict[str, Any] = Field(default_factory=dict)
    profile: ProfileData
    resume_file: ResumeFile | None = None
    credentials: dict[str, dict[str, str]] | None = None
    cover_letter: str | None = None
    dry_run: bool = True


class ApplyResult(BaseModel):
    """Outcome of a single apply attempt."""

    status: str  # "submitted" | "dry_run" | "failed"
    error: str | None = None
    payload: dict[str, Any] | None = None
    external_application_id: str | None = None
