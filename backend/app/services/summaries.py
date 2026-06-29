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
from app.scrapers.types import JobPosting
from app.summarizers import SummaryContext, get_summarizer
from app.summarizers.base import Summarizer

logger = get_logger(__name__)

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
    ) -> None:
        """Set `posting.summary` in place for each posting; no-op when disabled."""
        if not self._settings.summaries_enabled or not postings:
            return

        provider = str(self._settings.summary_provider)
        ctx = SummaryContext(search_name=search_name, filters=filters or {})
        try:
            summarizer = self._factory(provider)
            blurbs = summarizer.summarize(ctx, postings)
        except Exception as exc:  # provider/network/credentials are best-effort
            logger.warning("summary provider %s failed: %s", provider, exc)
            return

        max_chars = int(self._settings.summary_max_chars)
        for posting, blurb in zip(postings, blurbs, strict=False):
            text = (blurb or "").strip()
            if text:
                posting.summary = _truncate(text, max_chars)


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip() + "\u2026"
