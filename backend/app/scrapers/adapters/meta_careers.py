"""Meta Careers (metacareers.com) job-search adapter.

Meta's careers portal loads search results via a Relay/GraphQL POST on the same
origin. A short-lived ``lsd`` anti-CSRF token is embedded in the job search
page HTML.

Config / context:
  - `query_url`: metacareers.com job search URL.
  - `config["q"]` / `config["search_text"]`: keyword filter.
  - `config["company"]`: display company name (defaults to ``Meta``).
  - `config["max_results"]`: cap on jobs returned (default 200).
  - `config["graphql_doc_id"]`: override Relay persisted query id (optional).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.scrapers.adapters.meta_careers_graphql import (
    extract_lsd_token,
    parse_graphql_json,
)
from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

_ORIGIN = "https://www.metacareers.com"
_GRAPHQL_PATH = "/graphql"
_SEARCH_PATHS = {"/jobsearch", "/jobs", "/jobsearch/"}
_DEFAULT_COMPANY = "Meta"
_DEFAULT_DOC_ID = "27506805582236862"
_DEFAULT_ASBD_ID = "359341"
_DEFAULT_MAX_RESULTS = 200
_MAX_RESULTS_CAP = 500
_HOST_RE = re.compile(
    r"^(?:www\.)?(?:metacareers|facebookcareers)\.com$",
    re.IGNORECASE,
)
_QUERY_NAME = "CareersJobSearchResultsDataQuery"


@register_scraper("meta_careers")
class MetaCareersScraper(Scraper):
    """Fetch postings from Meta Careers via the public GraphQL search query."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
        page_html = self.http.get_text(target.search_page_url)
        lsd = extract_lsd_token(page_html)
        body = self.http.post_form(
            f"{_ORIGIN}{_GRAPHQL_PATH}",
            data=self._graphql_form(target, lsd=lsd),
            headers={
                "x-fb-friendly-name": _QUERY_NAME,
                "x-fb-lsd": lsd,
                "x-asbd-id": _DEFAULT_ASBD_ID,
            },
        )
        postings = parse_graphql_json(body, company=target.company)
        return postings[: target.max_results]

    @staticmethod
    def _resolve(ctx: ScrapeContext) -> _SearchTarget:
        company = str(ctx.config.get("company") or _DEFAULT_COMPANY)
        keyword = MetaCareersScraper._keyword(ctx)
        doc_id = str(ctx.config.get("graphql_doc_id") or _DEFAULT_DOC_ID).strip()
        max_results = MetaCareersScraper._max_results(ctx.config)
        search_page_url = MetaCareersScraper._search_page_url(ctx, keyword=keyword)
        return _SearchTarget(
            search_page_url=search_page_url,
            keyword=keyword or None,
            company=company,
            doc_id=doc_id,
            max_results=max_results,
        )

    @staticmethod
    def _search_page_url(ctx: ScrapeContext, *, keyword: str) -> str:
        if ctx.query_url:
            parsed = urlparse(ctx.query_url.strip())
            host = parsed.netloc.lower()
            if not _HOST_RE.match(host):
                raise ValueError("meta_careers scraper requires a metacareers.com URL")
            path = parsed.path.rstrip("/") or "/"
            if path.startswith("/jobs/"):
                raise ValueError("meta_careers query_url must be a job search page, not a posting")
            if path not in _SEARCH_PATHS:
                raise ValueError("meta_careers query_url must be a job search page")
            return ctx.query_url.strip()

        base = f"{_ORIGIN}/jobsearch/"
        if keyword:
            return f"{base}?q={keyword}"
        return base

    @staticmethod
    def _keyword(ctx: ScrapeContext) -> str:
        if ctx.query_url:
            parsed = urlparse(ctx.query_url.strip())
            params = parse_qs(parsed.query, keep_blank_values=True)
            for key in ("q", "query", "keywords"):
                values = params.get(key)
                if values and values[0].strip():
                    return values[0].strip()

        for key in ("q", "search_text", "keywords"):
            value = ctx.config.get(key)
            if value:
                return str(value).strip()
        for key in ("keywords_include", "keywords"):
            value = ctx.filters.get(key)
            if value:
                return str(value).strip()
        return ""

    @staticmethod
    def _max_results(config: dict[str, Any]) -> int:
        raw = config.get("max_results", _DEFAULT_MAX_RESULTS)
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ValueError("max_results must be a positive integer")
        limit = int(raw)
        if limit <= 0:
            raise ValueError("max_results must be a positive integer")
        return min(limit, _MAX_RESULTS_CAP)

    @staticmethod
    def _graphql_form(target: _SearchTarget, *, lsd: str) -> dict[str, str]:
        variables: dict[str, Any] = {
            "search_input": {
                "q": target.keyword,
                "divisions": [],
                "offices": [],
                "roles": [],
                "leadership_levels": [],
                "saved_jobs": [],
                "saved_searches": [],
                "sub_teams": [],
                "teams": [],
                "is_leadership": False,
                "is_remote_only": False,
                "sort_by_new": False,
                "page": 1,
                "results_per_page": None,
            }
        }
        return {
            "lsd": lsd,
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": _QUERY_NAME,
            "variables": json.dumps(variables, separators=(",", ":")),
            "doc_id": target.doc_id,
        }


@dataclass(frozen=True, slots=True)
class _SearchTarget:
    search_page_url: str
    keyword: str | None
    company: str
    doc_id: str
    max_results: int
