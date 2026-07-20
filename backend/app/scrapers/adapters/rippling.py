"""Rippling ATS public job-board adapter.

Rippling-backed employers expose a zero-auth board API:

  GET https://api.rippling.com/platform/api/ats/v1/board/<board>/jobs

Careers UI lives at ``https://ats.rippling.com/<board>/jobs``. The API returns
a JSON **array**; the same job UUID may appear once per work location — this
adapter collapses those rows and joins locations.

Config / context:
  - ``query_url``: ATS board URL, API URL, or empty.
  - ``config["board"]``: board slug (required when ``query_url`` is empty).
  - ``config["company"]``: display name (defaults to humanized board slug).
  - ``config["keywords"]`` / ``q`` / ``search``: optional client-side title filter.
  - ``config["max_results"]``: cap after dedupe (default 1000).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

_API_HOST = "api.rippling.com"
_ATS_HOST = "ats.rippling.com"
_API_PREFIX = "/platform/api/ats/v1/board/"
_BOARD_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$")
_DEFAULT_MAX_RESULTS = 1000
_MAX_RESULTS_CAP = 2000


@dataclass(frozen=True, slots=True)
class _BoardTarget:
    board: str
    company: str
    keywords: str


@register_scraper("rippling")
class RipplingScraper(Scraper):
    """Fetch postings from a Rippling public ATS board API."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
        max_results = self._max_results(ctx.config)
        data = self.http.get_json(self._api_url(target.board))
        if not isinstance(data, list):
            raise ValueError("rippling API returned unexpected payload (expected a JSON array)")

        merged: dict[str, JobPosting] = {}
        order: list[str] = []
        keywords = target.keywords.casefold()

        for raw in data:
            posting = self._to_posting(raw, target)
            if posting is None:
                continue
            if keywords and keywords not in posting.title.casefold():
                continue
            existing = merged.get(posting.external_id)
            if existing is None:
                if len(order) >= max_results:
                    continue
                merged[posting.external_id] = posting
                order.append(posting.external_id)
            else:
                merged[posting.external_id] = self._merge_locations(existing, posting.location)

        return [merged[key] for key in order]

    @classmethod
    def _resolve(cls, ctx: ScrapeContext) -> _BoardTarget:
        board = str(ctx.config.get("board") or "").strip()
        if ctx.query_url:
            board = cls._board_from_url(ctx.query_url.strip()) or board
        board = cls._validate_board(board)
        company = str(ctx.config.get("company") or "").strip() or _humanize_slug(board)
        return _BoardTarget(board=board, company=company, keywords=cls._keywords(ctx))

    @classmethod
    def _board_from_url(cls, query_url: str) -> str:
        parsed = urlparse(query_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("rippling scraper query_url must be an http(s) board or API URL")
        host = parsed.netloc.lower()
        parts = [part for part in parsed.path.split("/") if part]
        if host == _ATS_HOST:
            if not parts:
                raise ValueError("rippling scraper could not determine board from query_url")
            return parts[0]
        if host == _API_HOST:
            # /platform/api/ats/v1/board/<board>/jobs
            if len(parts) >= 6 and "/".join(parts[:5]) == "platform/api/ats/v1/board":
                return parts[5]
            raise ValueError("rippling scraper could not determine board from API query_url")
        raise ValueError(
            "rippling scraper query_url must be an ats.rippling.com board URL "
            "or api.rippling.com board API URL"
        )

    @staticmethod
    def _validate_board(board: str) -> str:
        cleaned = board.strip()
        if not cleaned or not _BOARD_RE.fullmatch(cleaned):
            raise ValueError(
                "rippling scraper needs a query_url or config.board "
                "(alphanumeric board slug, optional internal hyphens)"
            )
        return cleaned

    @staticmethod
    def _api_url(board: str) -> str:
        return f"https://{_API_HOST}{_API_PREFIX}{board}/jobs"

    @staticmethod
    def _keywords(ctx: ScrapeContext) -> str:
        for key in ("keywords", "q", "search", "search_text"):
            raw = ctx.config.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        filters = ctx.filters if isinstance(ctx.filters, dict) else {}
        for key in ("keywords", "q", "search"):
            raw = filters.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return ""

    @staticmethod
    def _max_results(config: dict[str, Any]) -> int:
        raw = config.get("max_results", _DEFAULT_MAX_RESULTS)
        if not isinstance(raw, int | float) or isinstance(raw, bool):
            raise ValueError("max_results must be a positive integer")
        value = int(raw)
        if value <= 0:
            raise ValueError("max_results must be a positive integer")
        return min(value, _MAX_RESULTS_CAP)

    @classmethod
    def _to_posting(cls, raw: object, target: _BoardTarget) -> JobPosting | None:
        if not isinstance(raw, dict):
            return None
        external_id = str(raw.get("uuid") or "").strip()
        title = str(raw.get("name") or "").strip()
        if not external_id or not title:
            return None
        url = str(raw.get("url") or "").strip()
        if not url:
            url = f"https://{_ATS_HOST}/{target.board}/jobs/{external_id}"
        return JobPosting(
            external_id=external_id,
            title=title,
            company=target.company,
            location=cls._location(raw.get("workLocation")),
            url=url,
            raw=raw,
        )

    @staticmethod
    def _location(value: object) -> str:
        if isinstance(value, dict):
            label = value.get("label")
            if isinstance(label, str) and label.strip():
                return label.strip()
            return ""
        if isinstance(value, str) and value.strip():
            return value.strip()
        return ""

    @staticmethod
    def _merge_locations(existing: JobPosting, new_location: str) -> JobPosting:
        if not new_location or new_location in existing.location.split("; "):
            return existing
        location = new_location if not existing.location else f"{existing.location}; {new_location}"
        return JobPosting(
            external_id=existing.external_id,
            title=existing.title,
            company=existing.company,
            location=location,
            url=existing.url,
            posted_at=existing.posted_at,
            summary=existing.summary,
            raw=existing.raw,
        )


def _humanize_slug(slug: str) -> str:
    cleaned = slug.replace("-", " ").replace("_", " ").strip()
    return cleaned.title() if cleaned else slug
