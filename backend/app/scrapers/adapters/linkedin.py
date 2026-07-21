"""LinkedIn job-search adapter.

LinkedIn exposes a guest pagination endpoint used by the public search UI:
  GET https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search

It returns HTML job-card fragments (not JSON). Session cookies from Site
credentials help when LinkedIn serves an auth wall or rate-limits anonymous
clients.

Config / context:
  - `query_url`: full LinkedIn search URL (e.g.
    `https://www.linkedin.com/jobs/search/?keywords=python&location=remote`).
  - `config["keywords"]` / `config["location"]`: when building the search URL.
  - `config["max_results"]`: cap on jobs fetched across pages (default 50).
  - `config["page_size"]`: pagination step (default 25; LinkedIn uses 25).

This adapter is opt-in only and is not auto-detected from URLs.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from selectolax.parser import HTMLParser

from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

_GUEST_SEARCH_API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
_LINKEDIN_HOST_RE = re.compile(r"^(?:[a-z]{2}|www)\.linkedin\.com$|^linkedin\.com$", re.IGNORECASE)
_JOB_ID_FROM_URN_RE = re.compile(r"urn:li:jobPosting:(\d+)")
_JOB_ID_FROM_URL_RE = re.compile(r"-(\d+)(?:\?|$)")
_AUTH_MARKERS = (
    "authwall",
    "Sign in to LinkedIn",
    "Join LinkedIn",
    "checkpoint/challenge",
)
_DEFAULT_MAX_RESULTS = 50
_DEFAULT_PAGE_SIZE = 25
_MAX_RESULTS_CAP = 1000


@register_scraper("linkedin")
class LinkedInScraper(Scraper):
    """Fetch postings from a LinkedIn keyword/location search."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
        max_results = self._max_results(ctx.config)
        page_size = self._page_size(ctx.config)
        postings: list[JobPosting] = []
        seen: set[str] = set()
        offset = 0

        while len(postings) < max_results:
            page_url = self._guest_page_url(target.search_params, offset)
            html = self.http.get_text(page_url)
            self._reject_auth_wall(html)
            jobs = _parse_cards(html)
            if not jobs:
                break
            for job in jobs:
                if job.external_id in seen:
                    continue
                seen.add(job.external_id)
                postings.append(job)
                if len(postings) >= max_results:
                    break
            if len(jobs) < page_size:
                break
            offset += page_size

        return postings

    @staticmethod
    def _resolve(ctx: ScrapeContext) -> _SearchTarget:
        if ctx.query_url:
            parsed = urlparse(ctx.query_url.strip())
            host = parsed.netloc.lower()
            if not _LINKEDIN_HOST_RE.match(host):
                raise ValueError("linkedin scraper requires a linkedin.com search URL")
            path = parsed.path.rstrip("/") or "/"
            if not path.startswith("/jobs/search"):
                raise ValueError("linkedin scraper query_url must be a /jobs/search page")
            params = _flatten_query_params(parse_qs(parsed.query, keep_blank_values=True))
            if not params.get("keywords") and not params.get("location"):
                raise ValueError(
                    "linkedin search URL must include keywords and/or location query params"
                )
            return _SearchTarget(search_params=params)

        config = ctx.config
        keywords = str(
            config.get("keywords") or config.get("q") or config.get("keyword") or ""
        ).strip()
        location = str(config.get("location") or config.get("l") or "").strip()
        if not keywords and not location:
            raise ValueError("linkedin scraper needs a query_url or config keywords/location")
        search_params: dict[str, str] = {}
        if keywords:
            search_params["keywords"] = keywords
        if location:
            search_params["location"] = location
        for key in ("geoId", "f_TPR", "f_WT", "f_C", "f_E", "f_JT"):
            raw = config.get(key)
            if raw is not None and str(raw).strip():
                search_params[key] = str(raw).strip()
        return _SearchTarget(search_params=search_params)

    @staticmethod
    def _guest_page_url(search_params: dict[str, str], start: int) -> str:
        params = dict(search_params)
        if start > 0:
            params["start"] = str(start)
        elif "start" in params:
            params.pop("start")
        query = urlencode(params)
        return f"{_GUEST_SEARCH_API}?{query}" if query else _GUEST_SEARCH_API

    @staticmethod
    def _reject_auth_wall(html: str) -> None:
        lowered = html.lower()
        if any(marker.lower() in lowered for marker in _AUTH_MARKERS):
            raise ValueError(
                "linkedin returned an auth wall; add session cookies via Site credentials "
                "or retry later"
            )

    @staticmethod
    def _max_results(config: dict[str, Any]) -> int:
        raw = config.get("max_results", _DEFAULT_MAX_RESULTS)
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ValueError("max_results must be a positive integer")
        value = int(raw)
        if value <= 0:
            raise ValueError("max_results must be a positive integer")
        return min(value, _MAX_RESULTS_CAP)

    @staticmethod
    def _page_size(config: dict[str, Any]) -> int:
        raw = config.get("page_size", _DEFAULT_PAGE_SIZE)
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ValueError("page_size must be a positive integer")
        value = int(raw)
        if value <= 0:
            raise ValueError("page_size must be a positive integer")
        return value


class _SearchTarget:
    __slots__ = ("search_params",)

    def __init__(self, *, search_params: dict[str, str]) -> None:
        self.search_params = search_params


def _flatten_query_params(params: dict[str, list[str]]) -> dict[str, str]:
    flattened: dict[str, str] = {}
    for key, values in params.items():
        if key == "start":
            continue
        if values:
            flattened[key] = values[0]
    return flattened


def _parse_cards(html: str) -> list[JobPosting]:
    tree = HTMLParser(html)
    postings: list[JobPosting] = []
    for card in tree.css("div.job-search-card, div.base-search-card[data-entity-urn]"):
        posting = _card_to_posting(card)
        if posting is not None:
            postings.append(posting)
    return postings


def _card_to_posting(card: Any) -> JobPosting | None:
    urn = (card.attributes or {}).get("data-entity-urn", "")
    external_id = _job_id_from_urn(urn)
    link = card.css_first("a.base-card__full-link")
    href = (link.attributes or {}).get("href", "").strip() if link else ""
    if not external_id and href:
        external_id = _job_id_from_url(href)
    title_node = card.css_first("h3.base-search-card__title")
    title = title_node.text(strip=True) if title_node else ""
    if not external_id or not title:
        return None
    company_node = card.css_first("h4.base-search-card__subtitle a, h4.base-search-card__subtitle")
    company = company_node.text(strip=True) if company_node else ""
    location_node = card.css_first("span.job-search-card__location")
    location = location_node.text(strip=True) if location_node else ""
    url = _normalize_job_url(href, external_id)
    posted_at = None
    time_node = card.css_first("time.job-search-card__listdate")
    if time_node is not None:
        raw_dt = (time_node.attributes or {}).get("datetime", "").strip()
        if raw_dt:
            try:
                posted_at = datetime.fromisoformat(raw_dt).replace(tzinfo=UTC)
            except ValueError:
                posted_at = None
    return JobPosting(
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        url=url,
        posted_at=posted_at,
        raw={"entity_urn": urn, "href": href},
    )


def _job_id_from_urn(urn: str) -> str:
    match = _JOB_ID_FROM_URN_RE.search(urn)
    return match.group(1) if match else ""


def _job_id_from_url(url: str) -> str:
    match = _JOB_ID_FROM_URL_RE.search(url)
    return match.group(1) if match else ""


def _normalize_job_url(href: str, external_id: str) -> str:
    if href:
        parsed = urlparse(href.split("?", 1)[0])
        if parsed.scheme and parsed.netloc:
            return urlunparse(parsed)
    return f"https://www.linkedin.com/jobs/view/{external_id}"
