"""Generate "why this matches" blurbs and attach them to postings.

Thin orchestration over the summarizer registry: gate on config, pick the
configured provider, and degrade gracefully. A summary is presentational and
best-effort, so any provider failure must never break the pipeline — it just
leaves the blurb empty.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.config import settings as default_settings
from app.core.logging import get_logger
from app.email_classifiers.sanitize import looks_like_prompt_injection
from app.models.user import User
from app.scrapers.types import JobPosting
from app.summarizers import SummaryContext, get_summarizer
from app.summarizers.base import Summarizer
from app.summarizers.runtime_settings import resolve_summary_settings

logger = get_logger(__name__)

LLM_PROVIDERS = frozenset({"openai", "gemini", "anthropic", "llamacpp"})
SummarizerFactory = Callable[[str], Summarizer]


class SummaryService:
    def __init__(
        self,
        *,
        summarizer_factory: SummarizerFactory = get_summarizer,
        settings: Any = default_settings,
    ) -> None:
        self._factory = summarizer_factory
        self._settings = settings

    def annotate(
        self,
        postings: list[JobPosting],
        *,
        search_name: str | None = None,
        filters: dict[str, Any] | None = None,
        user: User | None = None,
    ) -> None:
        """Set `posting.summary` in place for each posting; no-op when disabled."""
        runtime_settings = resolve_summary_settings(self._settings, user)
        if not runtime_settings.summaries_enabled or not postings:
            return

        provider = str(runtime_settings.summary_provider)
        if provider in LLM_PROVIDERS and self._postings_look_injected(postings):
            logger.warning(
                "summary: scraped posting fields matched injection patterns; "
                "forcing heuristic summarizer"
            )
            provider = "heuristic"

        ctx = SummaryContext(search_name=search_name, filters=filters or {})
        try:
            summarizer = self._factory(provider, settings=runtime_settings)  # type: ignore[call-arg]
            blurbs = summarizer.summarize(ctx, postings)
        except Exception as exc:  # provider/network/credentials are best-effort
            logger.warning("summary provider %s failed: %s", provider, exc)
            return

        max_chars = int(runtime_settings.summary_max_chars)
        for posting, blurb in zip(postings, blurbs, strict=False):
            text = (blurb or "").strip()
            if text:
                posting.summary = _truncate(text, max_chars)

    @staticmethod
    def _postings_look_injected(postings: list[JobPosting]) -> bool:
        """True when any scraped title/company/location matches injection patterns."""
        for posting in postings:
            parts = (posting.title, posting.company, posting.location)
            if any(looks_like_prompt_injection(part) for part in parts if part):
                return True
        return False


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip() + "\u2026"
