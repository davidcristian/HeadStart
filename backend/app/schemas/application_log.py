"""Application log response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.application_artifact import ApplicationArtifactMeta


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
    tailored_resume_artifact: ApplicationArtifactMeta | None = None
    created_at: datetime
