"""Job feed (seen job) request/response schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

JobStatus = Literal["new", "seen", "applied", "archived", "closed"]
UserJobStatus = Literal["seen", "applied", "archived"]


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    search_id: int
    external_id: str
    title: str
    company: str
    location: str
    salary: str
    url: str
    summary: str
    status: JobStatus
    first_seen_at: datetime
    applied_at: datetime | None = None


class JobUpdate(BaseModel):
    status: UserJobStatus = Field(description="User triage status; closed is set by the pipeline")


class JobApplyRequest(BaseModel):
    dry_run: bool = Field(default=False, description="Preview payload without submitting")
    cover_letter: str | None = Field(
        default=None,
        description="Optional cover letter override for this application",
    )


class JobApplyResult(BaseModel):
    status: str
    error: str | None = None
    payload: dict[str, Any] | None = None
    external_application_id: str | None = None
    job: JobRead | None = None
    application_log_id: int | None = Field(
        default=None,
        description="Queued live apply log id; poll GET /application-logs/{id} for status",
    )


class JobCoverLetterResult(BaseModel):
    cover_letter: str
    provider: str = Field(description="Generator key used (e.g. heuristic, openai)")
    fallback: bool = Field(
        default=False,
        description="True when an LLM provider failed and heuristic was used instead",
    )
