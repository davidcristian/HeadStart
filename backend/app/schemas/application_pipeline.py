"""Application pipeline response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.job import JobStatus

ApplicationPipelineStage = Literal[
    "queued",
    "apply_failed",
    "awaiting_reply",
    "ghosted",
    "closed",
    "archived",
]


class ApplicationAttemptSummary(BaseModel):
    """One live (non-preview) apply attempt in the pipeline timeline."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    error: str | None = None
    external_application_id: str | None = None
    created_at: datetime


class ApplicationPipelineRead(BaseModel):
    """Aggregated application status for one job in the user's pipeline."""

    job_id: int
    search_id: int
    title: str
    company: str
    location: str
    url: str
    job_status: JobStatus
    pipeline_stage: ApplicationPipelineStage
    applied_at: datetime | None = None
    ghosted_at: datetime | None = None
    latest_attempt: ApplicationAttemptSummary | None = None
    attempts: list[ApplicationAttemptSummary] = Field(
        default_factory=list,
        description="Chronological live apply attempts (oldest first)",
    )


class ApplicationPipelineListParams(BaseModel):
    stage: ApplicationPipelineStage | None = None
    limit: int = Field(default=100, ge=1, le=500)
