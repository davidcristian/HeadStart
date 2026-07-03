"""Shared helpers for LLM cover-letter adapters."""

from __future__ import annotations

from typing import Any


def extract_openai_content(data: dict[str, Any]) -> str:
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("unexpected OpenAI response shape") from exc
    return str(content or "").strip()


def extract_gemini_content(data: dict[str, Any]) -> str:
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = parts[0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("unexpected Gemini response shape") from exc
    return str(text or "").strip()


def extract_anthropic_content(data: dict[str, Any]) -> str:
    try:
        blocks = data["content"]
        text = blocks[0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("unexpected Anthropic response shape") from exc
    return str(text or "").strip()


def auth_headers(api_key: str) -> dict[str, str]:
    key = api_key.strip()
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}"}
