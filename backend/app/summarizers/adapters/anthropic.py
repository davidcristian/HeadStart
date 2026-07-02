"""Anthropic Claude summarizer (opt-in).

Generates a one-sentence "why this matches" blurb per job via the Anthropic
Messages API. Enable with `SUMMARY_PROVIDER=anthropic` and
`ANTHROPIC_API_KEY` (see app/core/config.py).

Network and credentials live here, at the edge. Failures raise; the calling
`SummaryService` swallows them so a flaky LLM never blocks notifications.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings as default_settings
from app.core.logging import get_logger
from app.scrapers.types import JobPosting
from app.summarizers.adapters.openai import _SYSTEM_PROMPT, _user_prompt
from app.summarizers.base import Summarizer, register_summarizer
from app.summarizers.types import SummaryContext

logger = get_logger(__name__)


@register_summarizer("anthropic")
class AnthropicSummarizer(Summarizer):
    """Summarize postings with Anthropic Claude."""

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
        api_key = str(getattr(self._settings, "anthropic_api_key", "") or "").strip()
        if not api_key:
            raise ValueError("anthropic summarizer requires ANTHROPIC_API_KEY")
        base_url = str(self._settings.anthropic_base_url).rstrip("/")
        model = str(self._settings.anthropic_model)
        api_version = str(self._settings.anthropic_api_version)
        url = f"{base_url}/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": api_version,
        }
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
            "max_tokens": 80,
            "system": _SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": _user_prompt(ctx, job)},
            ],
        }
        resp = self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return _extract_content(resp.json())

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def _extract_content(data: dict[str, Any]) -> str:
    try:
        blocks = data["content"]
        text = blocks[0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("unexpected Anthropic response shape") from exc
    return str(text or "").strip()
