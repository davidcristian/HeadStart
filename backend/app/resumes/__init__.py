"""Pluggable resume curators for job-tailored LaTeX → PDF generation."""

from app.resumes.base import (
    ResumeCurator,
    available_resume_curators,
    get_resume_curator,
    register_resume_curator,
)
from app.resumes.types import CuratedResumeFields, ResumeCurationContext

__all__ = [
    "CuratedResumeFields",
    "ResumeCurationContext",
    "ResumeCurator",
    "available_resume_curators",
    "get_resume_curator",
    "register_resume_curator",
]
