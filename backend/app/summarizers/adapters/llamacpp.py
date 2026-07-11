"""llama.cpp local summarizer (dev-only).

Calls a llama.cpp `llama-server` instance exposing OpenAI-compatible Chat
Completions at `LLAMACPP_BASE_URL` (default `http://localhost:8080/v1`).
Enable with `SUMMARY_PROVIDER=llamacpp`. No API key is required for a default
local server; set `LLAMACPP_API_KEY` only when your server expects one.

Network lives here, at the edge. Failures raise; `SummaryService` swallows them
so a down local model never blocks notifications.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.llm_common import auth_headers, extract_openai_content, llm_post
from app.core.config import settings as default_settings
from app.scrapers.types import JobPosting
from app.summarizers.base import Summarizer, register_summarizer
from app.summarizers.prompts import SYSTEM_PROMPT, user_prompt
from app.summarizers.types import SummaryContext


@register_summarizer("llamacpp")
class LlamaCppSummarizer(Summarizer):
    """Summarize postings with a local llama.cpp OpenAI-compatible server."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        settings: Any = default_settings,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=60.0)

    def summarize(self, ctx: SummaryContext, jobs: list[JobPosting]) -> list[str]:
        base_url = str(self._settings.llamacpp_base_url).rstrip("/")
        model = str(self._settings.llamacpp_model)
        url = f"{base_url}/chat/completions"
        headers = auth_headers(str(getattr(self._settings, "llamacpp_api_key", "") or ""))
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
