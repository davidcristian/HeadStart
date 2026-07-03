"""Shared AI purpose routing for summaries, cover letters, and future agents."""

from app.ai.purposes import AI_PURPOSES, AiPurposeId
from app.ai.runtime_settings import resolve_ai_settings, resolve_summary_settings

__all__ = [
    "AI_PURPOSES",
    "AiPurposeId",
    "resolve_ai_settings",
    "resolve_summary_settings",
]
