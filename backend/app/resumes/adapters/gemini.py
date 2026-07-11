"""Google Gemini resume curator."""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.llm_common import extract_gemini_content, gemini_headers, gemini_url, llm_post
from app.core.config import settings as default_settings
from app.resumes.base import ResumeCurator, register_resume_curator
from app.resumes.prompts import SYSTEM_PROMPT, parse_curated_json, user_prompt
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
        url = gemini_url(str(self._settings.gemini_base_url), str(self._settings.gemini_model))
        headers = gemini_headers(api_key)
        resp = llm_post(self._client, url, json=payload, headers=headers)
        resp.raise_for_status()
        return parse_curated_json(extract_gemini_content(resp.json()), ctx)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
