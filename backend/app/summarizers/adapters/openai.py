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

from app.core.config import settings as default_settings
from app.core.logging import get_logger
from app.scrapers.types import JobPosting
from app.summarizers.base import Summarizer, register_summarizer
from app.summarizers.types import SummaryContext

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You help a job seeker triage new postings. In ONE short sentence (max 30 "
    "words), explain why a posting matches their saved search. Be concrete and "
    "specific; do not use markdown, quotes, or a leading label."
)


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
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(ctx, job)},
            ],
            "temperature": 0.3,
            "max_tokens": 80,
        }
        resp = self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return _extract_content(data)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def _user_prompt(ctx: SummaryContext, job: JobPosting) -> str:
    lines = ["Posting:"]
    if job.title:
        lines.append(f"- Title: {job.title}")
    if job.company:
        lines.append(f"- Company: {job.company}")
    if job.location:
        lines.append(f"- Location: {job.location}")
    lines.append("")
    if ctx.search_name:
        lines.append(f"Saved search: {ctx.search_name}")
    if ctx.filters:
        lines.append(f"Search filters: {_describe_filters(ctx.filters)}")
    lines.append("Explain in one sentence why this posting matches the search.")
    return "\n".join(lines)


def _describe_filters(filters: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("keywords", "keywords_include", "keywords_exclude", "location", "workplace"):
        value = filters.get(key)
        if value:
            parts.append(f"{key}={value}")
    min_salary = filters.get("min_salary")
    if min_salary:
        currency = filters.get("salary_currency") or "USD"
        parts.append(f"min_salary={min_salary} {currency}")
    return "; ".join(parts) if parts else "none"


def _extract_content(data: dict[str, Any]) -> str:
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("unexpected OpenAI response shape") from exc
    return str(content or "").strip()
