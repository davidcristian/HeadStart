"""Anthropic resume curator."""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.llm_common import extract_anthropic_content, llm_post
from app.core.config import settings as default_settings
from app.resumes.base import ResumeCurator, register_resume_curator
from app.resumes.prompts import SYSTEM_PROMPT, parse_curated_json, user_prompt
from app.resumes.types import CuratedResumeFields, ResumeCurationContext


@register_resume_curator("anthropic")
class AnthropicResumeCurator(ResumeCurator):
    """Tailor resume placeholders with Anthropic Claude."""

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
        api_key = str(getattr(self._settings, "anthropic_api_key", "") or "").strip()
        if not api_key:
            raise ValueError("anthropic resume curator requires ANTHROPIC_API_KEY")
        base_url = str(self._settings.anthropic_base_url).rstrip("/")
        model = str(self._settings.anthropic_model)
        version = str(self._settings.anthropic_api_version)
        max_tokens = int(getattr(self._settings, "resume_curation_max_tokens", 1200))
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt(ctx)}],
        }
        resp = llm_post(
            self._client,
            f"{base_url}/messages",
            json=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": version,
                "content-type": "application/json",
            },
        )
        resp.raise_for_status()
        return parse_curated_json(extract_anthropic_content(resp.json()), ctx)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
