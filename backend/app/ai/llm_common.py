"""Shared HTTP helpers for the LLM provider adapters.

The AI families (`summarizers`, `resumes`, `cover_letters`, `email_classifiers`,
`reply_drafters`) each ship near-identical provider adapters. The response
shapes and auth schemes are provider-specific but family-independent, so they
live here once rather than being duplicated (or re-exported) per family.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote


def extract_openai_content(data: dict[str, Any]) -> str:
    """Pull the assistant text out of an OpenAI-compatible chat response."""
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("unexpected OpenAI response shape") from exc
    return str(content or "").strip()


def extract_gemini_content(data: dict[str, Any]) -> str:
    """Pull the generated text out of a Gemini `generateContent` response."""
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = parts[0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("unexpected Gemini response shape") from exc
    return str(text or "").strip()


def extract_anthropic_content(data: dict[str, Any]) -> str:
    """Pull the message text out of an Anthropic Messages response."""
    try:
        blocks = data["content"]
        text = blocks[0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("unexpected Anthropic response shape") from exc
    return str(text or "").strip()


def auth_headers(api_key: str) -> dict[str, str]:
    """Bearer auth header for OpenAI-compatible endpoints; empty when no key."""
    key = api_key.strip()
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}"}


def gemini_url(base_url: str, model: str) -> str:
    """Build the Gemini `generateContent` endpoint URL for a model."""
    base = base_url.rstrip("/")
    model_path = quote(model, safe="")
    return f"{base}/models/{model_path}:generateContent"


def gemini_headers(api_key: str) -> dict[str, str]:
    """Gemini auth header. Keeps the key out of the URL (it is loggable there)."""
    return {"x-goog-api-key": api_key.strip()}
