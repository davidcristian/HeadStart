"""llama.cpp local cover-letter generator (dev-only)."""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.llm_common import auth_headers, extract_openai_content
from app.core.config import settings as default_settings
from app.cover_letters.base import CoverLetterGenerator, register_cover_letter_generator
from app.cover_letters.prompts import SYSTEM_PROMPT, user_prompt
from app.cover_letters.types import CoverLetterContext


@register_cover_letter_generator("llamacpp")
class LlamaCppCoverLetterGenerator(CoverLetterGenerator):
    """Generate cover letters with a local llama.cpp OpenAI-compatible server."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        settings: Any = default_settings,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=90.0)

    def generate(self, ctx: CoverLetterContext) -> str:
        base_url = str(self._settings.llamacpp_base_url).rstrip("/")
        model = str(self._settings.llamacpp_model)
        url = f"{base_url}/chat/completions"
        headers = auth_headers(str(getattr(self._settings, "llamacpp_api_key", "") or ""))
        max_tokens = int(getattr(self._settings, "cover_letter_max_tokens", 900))
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt(ctx)},
            ],
            "temperature": 0.4,
            "max_tokens": max_tokens,
        }
        resp = self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return extract_openai_content(resp.json())

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
