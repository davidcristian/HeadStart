"""Resume curation context and curated field payloads."""

from pydantic import BaseModel, Field

from app.schemas.profile import ProfileData


class CuratedResumeFields(BaseModel):
    """Placeholder values injected into a LaTeX resume template."""

    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""
    job_title: str = ""
    company: str = ""
    summary: str = ""
    experience: str = ""
    education: str = ""
    skills: str = ""


class ResumeCurationContext(BaseModel):
    """Job posting and candidate profile inputs for one tailored resume."""

    job_title: str = ""
    company: str = ""
    location: str = ""
    salary: str = ""
    job_url: str = ""
    job_summary: str = ""
    profile: ProfileData = Field(default_factory=ProfileData)
