"""Google Gemini resume curator."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings as default_settings
from app.cover_letters.adapters.llm_common import extract_gemini_content
from app.resumes.adapters.llm_common import SYSTEM_PROMPT, user_prompt
from app.resumes.base import ResumeCurator, register_resume_curator
from app.resumes.prompts import parse_curated_json
from app.resumes.types import CuratedResumeFields, ResumeCurationContext


@register_resume_curator("gemini")
class GeminiResumeCurator(ResumeCurator):
    """Tailor resume placeholders with Google Gemini."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        settings: Any = default_settings,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=45.0)

    def curate(self, ctx: ResumeCurationContext) -> CuratedResumeFields:
        api_key = str(getattr(self._settings, "gemini_api_key", "") or "").strip()
        if not api_key:
            raise ValueError("gemini resume curator requires GEMINI_API_KEY")
        base_url = str(self._settings.gemini_base_url).rstrip("/")
        model = str(self._settings.gemini_model)
        model_path = quote(model, safe="")
        key_param = quote(api_key, safe="")
        max_tokens = int(getattr(self._settings, "resume_curation_max_tokens", 1200))
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt(ctx)}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }
        url = f"{base_url}/models/{model_path}:generateContent?key={key_param}"
        resp = self._client.post(url, json=payload)
        resp.raise_for_status()
        return parse_curated_json(extract_gemini_content(resp.json()), ctx)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
