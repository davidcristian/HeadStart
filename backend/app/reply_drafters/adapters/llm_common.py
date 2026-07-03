"""Shared helpers for LLM reply-drafter adapters."""

from app.cover_letters.adapters.llm_common import (
    auth_headers,
    extract_anthropic_content,
    extract_gemini_content,
    extract_openai_content,
)

__all__ = [
    "auth_headers",
    "extract_anthropic_content",
    "extract_gemini_content",
    "extract_openai_content",
]
