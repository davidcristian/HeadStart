"""Google Gemini cover-letter generator."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings as default_settings
from app.cover_letters.adapters.llm_common import extract_gemini_content
from app.cover_letters.base import CoverLetterGenerator, register_cover_letter_generator
from app.cover_letters.prompts import SYSTEM_PROMPT, user_prompt
from app.cover_letters.types import CoverLetterContext


@register_cover_letter_generator("gemini")
class GeminiCoverLetterGenerator(CoverLetterGenerator):
    """Generate cover letters with Google Gemini."""

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
        api_key = str(getattr(self._settings, "gemini_api_key", "") or "").strip()
        if not api_key:
            raise ValueError("gemini cover letter generator requires GEMINI_API_KEY")
        base_url = str(self._settings.gemini_base_url).rstrip("/")
        model = str(self._settings.gemini_model)
        model_path = quote(model, safe="")
        key_param = quote(api_key, safe="")
        url = f"{base_url}/models/{model_path}:generateContent?key={key_param}"
        max_tokens = int(getattr(self._settings, "cover_letter_max_tokens", 900))
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt(ctx)}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": max_tokens,
            },
        }
        resp = self._client.post(url, json=payload)
        resp.raise_for_status()
        return extract_gemini_content(resp.json())

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
