"""Job feed (seen job) request/response schemas."""

from datetime import datetime
from typing import Literal

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
    status: JobStatus
    first_seen_at: datetime


class JobUpdate(BaseModel):
    status: UserJobStatus = Field(description="User triage status; closed is set by the pipeline")
