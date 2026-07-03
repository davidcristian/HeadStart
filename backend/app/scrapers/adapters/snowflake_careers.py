"""Snowflake Careers adapter.

Snowflake hosts careers on careers.snowflake.com (Phenom) with Ashby behind the
scenes. The public Ashby Postings API is enabled for board ``snowflake``.

Config / context:
  - `query_url`: ``careers.snowflake.com`` search URL (optional).
  - `config["board"]`: Ashby board slug (default ``snowflake``).
  - `config["q"]` / `config["search"]` / `config["search_text"]`: client-side
    keyword filter applied after fetch.
  - `config["company"]`: display company name (defaults to ``Snowflake``).
  - `config["include_compensation"]`: optional bool; adds salary data from Ashby.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.scrapers.adapters.ashby_parse import api_url, parse_ashby_board_payload
from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

_DEFAULT_BOARD = "snowflake"
_DEFAULT_COMPANY = "Snowflake"
_HOST_RE = re.compile(r"^careers\.snowflake\.com$", re.IGNORECASE)
_SEARCH_PATH_RE = re.compile(r"^/(?:[a-z]{2}/[a-z]{2}/)?search-results/?$", re.IGNORECASE)


@register_scraper("snowflake_careers")
class SnowflakeCareersScraper(Scraper):
    """Fetch postings from Snowflake Careers via the public Ashby board API."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
        data = self.http.get_json(target.api_url)
        if not isinstance(data, dict):
            raise ValueError(
                "snowflake_careers API returned unexpected payload (expected a JSON object)"
            )
        postings = parse_ashby_board_payload(data, target.company)
        if target.keyword:
            postings = [job for job in postings if self._matches_keyword(job, target.keyword)]
        return postings

    @staticmethod
    def _resolve(ctx: ScrapeContext) -> _SearchTarget:
        config = ctx.config
        board = str(config.get("board") or _DEFAULT_BOARD)
        company = str(config.get("company") or _DEFAULT_COMPANY)
        include_compensation = bool(config.get("include_compensation", False))
        keyword = SnowflakeCareersScraper._keyword(ctx)

        if ctx.query_url:
            parsed = urlparse(ctx.query_url.strip())
            host = parsed.netloc.lower()
            if not _HOST_RE.match(host):
                raise ValueError("snowflake_careers scraper requires a careers.snowflake.com URL")
            if parsed.path not in {"", "/"} and not _SEARCH_PATH_RE.match(parsed.path):
                raise ValueError(
                    "snowflake_careers query_url must point at the careers search section"
                )

        return _SearchTarget(
            api_url=api_url(board, include_compensation),
            company=company,
            keyword=keyword,
        )

    @staticmethod
    def _keyword(ctx: ScrapeContext) -> str:
        for key in ("q", "search", "search_text", "keywords", "query"):
            value = ctx.config.get(key)
            if value:
                return str(value).strip().lower()
        for key in ("keywords_include", "keywords"):
            value = ctx.filters.get(key)
            if value:
                return str(value).strip().lower()
        return ""

    @staticmethod
    def _matches_keyword(job: JobPosting, keyword: str) -> bool:
        haystack = " ".join(
            part
            for part in (
                job.title,
                job.location,
                str(job.raw.get("department") or ""),
                str(job.raw.get("team") or ""),
            )
            if part
        ).lower()
        return keyword in haystack


@dataclass(frozen=True, slots=True)
class _SearchTarget:
    api_url: str
    company: str
    keyword: str
