"""Google Gemini summarizer (opt-in).

Generates a one-sentence "why this matches" blurb per job via the Gemini
`generateContent` REST API. Enable with `SUMMARY_PROVIDER=gemini` and
`GEMINI_API_KEY` (see app/core/config.py).

Network and credentials live here, at the edge. Failures raise; the calling
`SummaryService` swallows them so a flaky LLM never blocks notifications.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.llm_common import extract_gemini_content, gemini_headers, gemini_url
from app.core.config import settings as default_settings
from app.scrapers.types import JobPosting
from app.summarizers.base import Summarizer, register_summarizer
from app.summarizers.prompts import SYSTEM_PROMPT, user_prompt
from app.summarizers.types import SummaryContext


@register_summarizer("gemini")
class GeminiSummarizer(Summarizer):
    """Summarize postings with Google Gemini."""

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
        api_key = str(getattr(self._settings, "gemini_api_key", "") or "").strip()
        if not api_key:
            raise ValueError("gemini summarizer requires GEMINI_API_KEY")
        url = gemini_url(str(self._settings.gemini_base_url), str(self._settings.gemini_model))
        headers = gemini_headers(api_key)
        return [self._summarize_one(url, headers, ctx, job) for job in jobs]

    def _summarize_one(
        self, url: str, headers: dict[str, str], ctx: SummaryContext, job: JobPosting
    ) -> str:
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt(ctx, job)}],
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 80,
            },
        }
        resp = self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return extract_gemini_content(resp.json())

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
