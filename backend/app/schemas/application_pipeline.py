"""Application pipeline response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.application_artifact import ApplicationArtifactMeta
from app.schemas.inbox_reply_draft import ReplyDraftSummary
from app.schemas.job import JobStatus

ApplicationPipelineStage = Literal[
    "queued",
    "apply_failed",
    "awaiting_reply",
    "ghosted",
    "interview_pending",
    "rejected",
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
    tailored_resume_artifact: ApplicationArtifactMeta | None = None
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
    ghost_recovered_at: datetime | None = None
    interview_pending_at: datetime | None = None
    recruiter_rejection_at: datetime | None = None
    latest_attempt: ApplicationAttemptSummary | None = None
    attempts: list[ApplicationAttemptSummary] = Field(
        default_factory=list,
        description="Chronological live apply attempts (oldest first)",
    )
    latest_reply_draft: ReplyDraftSummary | None = None
    latest_draftable_classification_id: int | None = None


class ApplicationPipelineListParams(BaseModel):
    stage: ApplicationPipelineStage | None = None
    limit: int = Field(default=100, ge=1, le=500)
