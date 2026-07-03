"""OpenAI-backed resume curator."""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.llm_common import auth_headers, extract_openai_content
from app.core.config import settings as default_settings
from app.resumes.base import ResumeCurator, register_resume_curator
from app.resumes.prompts import SYSTEM_PROMPT, parse_curated_json, user_prompt
from app.resumes.types import CuratedResumeFields, ResumeCurationContext


@register_resume_curator("openai")
class OpenAIResumeCurator(ResumeCurator):
    """Tailor resume placeholders with an OpenAI-compatible chat model."""

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
        api_key = str(getattr(self._settings, "openai_api_key", "") or "").strip()
        if not api_key:
            raise ValueError("openai resume curator requires OPENAI_API_KEY")
        base_url = str(self._settings.openai_base_url).rstrip("/")
        model = str(self._settings.openai_model)
        max_tokens = int(getattr(self._settings, "resume_curation_max_tokens", 1200))
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt(ctx)},
            ],
            "temperature": 0.3,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        resp = self._client.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers=auth_headers(api_key),
        )
        resp.raise_for_status()
        return parse_curated_json(extract_openai_content(resp.json()), ctx)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
