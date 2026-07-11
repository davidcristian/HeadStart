"""OpenAI-backed summarizer (opt-in).

Generates a one-sentence "why this matches" blurb per job via an
OpenAI-compatible Chat Completions endpoint. Enable it by setting
`SUMMARY_PROVIDER=openai` and `OPENAI_API_KEY` (see app/core/config.py).

Network and credentials live here, at the edge. Failures raise; the calling
`SummaryService` swallows them so a flaky LLM never blocks notifications.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.llm_common import extract_openai_content, llm_post
from app.core.config import settings as default_settings
from app.scrapers.types import JobPosting
from app.summarizers.base import Summarizer, register_summarizer
from app.summarizers.prompts import SYSTEM_PROMPT, user_prompt
from app.summarizers.types import SummaryContext


@register_summarizer("openai")
class OpenAISummarizer(Summarizer):
    """Summarize postings with an OpenAI-compatible chat model."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        settings: Any = default_settings,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=20.0)

    def summarize(self, ctx: SummaryContext, jobs: list[JobPosting]) -> list[str]:
        api_key = str(getattr(self._settings, "openai_api_key", "") or "").strip()
        if not api_key:
            raise ValueError("openai summarizer requires OPENAI_API_KEY")
        base_url = str(self._settings.openai_base_url).rstrip("/")
        model = str(self._settings.openai_model)
        url = f"{base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        return [self._summarize_one(url, headers, model, ctx, job) for job in jobs]

    def _summarize_one(
        self,
        url: str,
        headers: dict[str, str],
        model: str,
        ctx: SummaryContext,
        job: JobPosting,
    ) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt(ctx, job)},
            ],
            "temperature": 0.3,
            "max_tokens": 80,
        }
        resp = llm_post(self._client, url, json=payload, headers=headers)
        resp.raise_for_status()
        return extract_openai_content(resp.json())

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
