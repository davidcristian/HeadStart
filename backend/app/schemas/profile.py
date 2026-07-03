"""Application profile request/response schemas.

The profile holds the candidate data an auto-apply flow needs. It is PII and is
encrypted at rest, but — unlike write-only site-credential secrets — it is
returned in full to its owner so they can review and edit it. `ProfileData` is
both the write body (full replacement on PUT) and the core of the read view.
"""

from __future__ import annotations

import base64
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_RESUME_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)

ALLOWED_RESUME_TEMPLATE_CONTENT_TYPES = frozenset(
    {
        "application/x-tex",
        "application/x-latex",
        "text/plain",
        "text/x-tex",
    }
)


class ProfileLinks(BaseModel):
    linkedin: str = Field(default="", max_length=500)
    github: str = Field(default="", max_length=500)
    website: str = Field(default="", max_length=500)


class WorkExperienceEntry(BaseModel):
    """One prior role used by Workday auto-apply and future apply adapters."""

    job_title: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=200)
    start_month: int | None = Field(default=None, ge=1, le=12)
    start_year: int | None = Field(default=None, ge=1900, le=2100)
    end_month: int | None = Field(default=None, ge=1, le=12)
    end_year: int | None = Field(default=None, ge=1900, le=2100)
    is_current: bool = False
    description: str = Field(default="", max_length=10_000)


class EducationEntry(BaseModel):
    """One education record used by Workday auto-apply and future apply adapters."""

    school: str = Field(default="", max_length=200)
    degree: str = Field(default="", max_length=200)
    field_of_study: str = Field(default="", max_length=200)
    start_year: int | None = Field(default=None, ge=1900, le=2100)
    end_year: int | None = Field(default=None, ge=1900, le=2100)
    gpa: str = Field(default="", max_length=20)


class LanguageEntry(BaseModel):
    """One language used by Workday auto-apply and future apply adapters."""

    language: str = Field(default="", max_length=100)
    proficiency: str = Field(default="", max_length=100)
    is_native: bool = False


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
    work_experience: list[WorkExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    languages: list[LanguageEntry] = Field(default_factory=list)

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, value: list[str]) -> list[str]:
        """Cap skill count and name length for storage and apply payloads."""
        if len(value) > 100:
            raise ValueError("skills cannot exceed 100 entries")
        for skill in value:
            if len(skill) > 200:
                raise ValueError("each skill name cannot exceed 200 characters")
        return value


class ResumeFileMeta(BaseModel):
    """Resume attachment metadata returned to the profile owner (no file bytes)."""

    filename: str
    content_type: str
    size_bytes: int = Field(ge=0)


class ResumeFile(ResumeFileMeta):
    """Decrypted resume bytes used when submitting applications."""

    data: bytes


class ResumeTemplateMeta(BaseModel):
    """LaTeX resume template metadata returned to the profile owner."""

    filename: str
    size_bytes: int = Field(ge=0)


class ResumeTemplateStored(BaseModel):
    """LaTeX resume template as stored inside the encrypted profile JSON blob."""

    filename: str
    data_b64: str

    def to_meta(self) -> ResumeTemplateMeta:
        raw = base64.b64decode(self.data_b64)
        return ResumeTemplateMeta(filename=self.filename, size_bytes=len(raw))

    @classmethod
    def from_bytes(cls, *, filename: str, data: bytes) -> ResumeTemplateStored:
        return cls(
            filename=filename,
            data_b64=base64.b64encode(data).decode("ascii"),
        )

    def decode_tex(self) -> str:
        """Decode stored template bytes as UTF-8 LaTeX source."""
        return base64.b64decode(self.data_b64).decode("utf-8")


class ResumeFileStored(BaseModel):
    """Resume attachment as stored inside the encrypted profile JSON blob."""

    filename: str
    content_type: str
    data_b64: str

    def to_resume_file(self) -> ResumeFile:
        """Decode stored base64 into bytes for apply adapters."""
        raw = base64.b64decode(self.data_b64)
        return ResumeFile(
            filename=self.filename,
            content_type=self.content_type,
            size_bytes=len(raw),
            data=raw,
        )

    @classmethod
    def from_bytes(cls, *, filename: str, content_type: str, data: bytes) -> ResumeFileStored:
        """Encode resume bytes for encrypted profile storage."""
        return cls(
            filename=filename,
            content_type=content_type,
            data_b64=base64.b64encode(data).decode("ascii"),
        )

    def to_meta(self) -> ResumeFileMeta:
        """Metadata only — safe for API responses and audit previews."""
        raw = base64.b64decode(self.data_b64)
        return ResumeFileMeta(
            filename=self.filename,
            content_type=self.content_type,
            size_bytes=len(raw),
        )


class ApplyProfile(ProfileData):
    """Profile payload passed to apply adapters, including optional resume bytes."""

    exists: bool = False
    resume_file: ResumeFile | None = None


class ProfileRead(ProfileData):
    # True once the user has saved a profile at least once; lets the UI tell an
    # empty default apart from a deliberately-cleared profile.
    exists: bool = False
    updated_at: datetime | None = None
    resume_file: ResumeFileMeta | None = None
    resume_template: ResumeTemplateMeta | None = None
