"""Cover letter generation context."""

from pydantic import BaseModel, Field

from app.schemas.profile import ProfileData


class CoverLetterContext(BaseModel):
    """Job posting and candidate profile inputs for one cover letter."""

    job_title: str = ""
    company: str = ""
    location: str = ""
    salary: str = ""
    job_url: str = ""
    job_summary: str = ""
    profile: ProfileData = Field(default_factory=ProfileData)
