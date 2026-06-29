"""Application profile request/response schemas.

The profile holds the candidate data an auto-apply flow needs. It is PII and is
encrypted at rest, but — unlike write-only site-credential secrets — it is
returned in full to its owner so they can review and edit it. `ProfileData` is
both the write body (full replacement on PUT) and the core of the read view.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProfileLinks(BaseModel):
    linkedin: str = Field(default="", max_length=500)
    github: str = Field(default="", max_length=500)
    website: str = Field(default="", max_length=500)


class ProfileData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=320)
    phone: str = Field(default="", max_length=50)
    location: str = Field(default="", max_length=200)
    links: ProfileLinks = Field(default_factory=ProfileLinks)
    resume_text: str = Field(default="", max_length=50_000)
    cover_letter_template: str = Field(default="", max_length=20_000)
    # Free-form answers to recurring application questions, e.g.
    # {"work_authorization": "US citizen", "notice_period": "2 weeks"}.
    answers: dict[str, str] = Field(default_factory=dict)


class ProfileRead(ProfileData):
    # True once the user has saved a profile at least once; lets the UI tell an
    # empty default apart from a deliberately-cleared profile.
    exists: bool = False
    updated_at: datetime | None = None
