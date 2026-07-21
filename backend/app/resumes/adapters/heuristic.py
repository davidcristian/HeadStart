"""Heuristic resume curator used as the offline default."""

from __future__ import annotations

from app.resumes.base import ResumeCurator, register_resume_curator
from app.resumes.fields import heuristic_fields
from app.resumes.types import CuratedResumeFields, ResumeCurationContext


@register_resume_curator("heuristic")
class HeuristicResumeCurator(ResumeCurator):
    """Tailor resume placeholders from profile data without external calls."""

    def __init__(self, *, settings: object | None = None) -> None:
        pass

    def curate(self, ctx: ResumeCurationContext) -> CuratedResumeFields:
        return heuristic_fields(ctx)
