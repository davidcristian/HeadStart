"""Google Gemini summarizer (opt-in).

Generates a one-sentence "why this matches" blurb per job via the Gemini
`generateContent` REST API. Enable with `SUMMARY_PROVIDER=gemini` and
`GEMINI_API_KEY` (see app/core/config.py).

Network and credentials live here, at the edge. Failures raise; the calling
`SummaryService` swallows them so a flaky LLM never blocks notifications.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings as default_settings
from app.core.logging import get_logger
from app.scrapers.types import JobPosting
from app.summarizers.adapters.openai import _SYSTEM_PROMPT, _user_prompt
from app.summarizers.base import Summarizer, register_summarizer
from app.summarizers.types import SummaryContext

logger = get_logger(__name__)


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
        base_url = str(self._settings.gemini_base_url).rstrip("/")
        model = str(self._settings.gemini_model)
        model_path = quote(model, safe="")
        key_param = quote(api_key, safe="")
        url = f"{base_url}/models/{model_path}:generateContent?key={key_param}"
        return [self._summarize_one(url, ctx, job) for job in jobs]

    def _summarize_one(self, url: str, ctx: SummaryContext, job: JobPosting) -> str:
        payload = {
            "systemInstruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": _user_prompt(ctx, job)}],
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 80,
            },
        }
        resp = self._client.post(url, json=payload)
        resp.raise_for_status()
        return _extract_content(resp.json())

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def _extract_content(data: dict[str, Any]) -> str:
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = parts[0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("unexpected Gemini response shape") from exc
    return str(text or "").strip()
