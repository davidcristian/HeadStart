"""Anthropic Claude cover-letter generator."""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.llm_common import extract_anthropic_content, llm_post
from app.core.config import settings as default_settings
from app.cover_letters.base import CoverLetterGenerator, register_cover_letter_generator
from app.cover_letters.prompts import SYSTEM_PROMPT, user_prompt
from app.cover_letters.types import CoverLetterContext


@register_cover_letter_generator("anthropic")
class AnthropicCoverLetterGenerator(CoverLetterGenerator):
    """Generate cover letters with Anthropic Claude."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        settings: Any = default_settings,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=45.0)

    def generate(self, ctx: CoverLetterContext) -> str:
        api_key = str(getattr(self._settings, "anthropic_api_key", "") or "").strip()
        if not api_key:
            raise ValueError("anthropic cover letter generator requires ANTHROPIC_API_KEY")
        base_url = str(self._settings.anthropic_base_url).rstrip("/")
        model = str(self._settings.anthropic_model)
        api_version = str(self._settings.anthropic_api_version)
        url = f"{base_url}/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": api_version,
        }
        max_tokens = int(getattr(self._settings, "cover_letter_max_tokens", 900))
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt(ctx)}],
        }
        resp = llm_post(self._client, url, json=payload, headers=headers)
        resp.raise_for_status()
        return extract_anthropic_content(resp.json())

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
