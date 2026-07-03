"""Shared helpers for LLM resume-curation adapters."""

from app.cover_letters.adapters.llm_common import (
    auth_headers,
    extract_anthropic_content,
    extract_gemini_content,
    extract_openai_content,
)
from app.resumes.prompts import SYSTEM_PROMPT, parse_curated_json, user_prompt

__all__ = [
    "SYSTEM_PROMPT",
    "auth_headers",
    "extract_anthropic_content",
    "extract_gemini_content",
    "extract_openai_content",
    "parse_curated_json",
    "user_prompt",
]
