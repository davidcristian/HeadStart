"""Workable public careers widget adapter.

Workable-backed employers expose a zero-auth widget JSON feed:

  GET https://apply.workable.com/api/v1/widget/accounts/<account>

Careers UI lives at ``https://apply.workable.com/<account>/``. The payload is a
JSON object with ``name`` / ``jobs``; each job is keyed by ``shortcode``.

Config / context:
  - ``query_url``: account careers URL, widget API URL, or empty.
  - ``config["account"]``: account slug (required when ``query_url`` is empty).
  - ``config["company"]``: display name (defaults to widget ``name``, then slug).
  - ``config["keywords"]`` / ``q`` / ``search``: optional client-side title filter.
  - ``config["max_results"]``: cap after filtering (default 1000).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

_APPLY_HOST = "apply.workable.com"
_WIDGET_PREFIX = "/api/v1/widget/accounts/"
_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$")
_RESERVED_PATHS = frozenset({"api", "j", "jobs", "login", "oauth", "static", "assets"})
_DEFAULT_MAX_RESULTS = 1000
_MAX_RESULTS_CAP = 2000


@dataclass(frozen=True, slots=True)
class _AccountTarget:
    account: str
    company: str
    keywords: str


@register_scraper("workable")
class WorkableScraper(Scraper):
    """Fetch postings from a Workable public widget careers feed."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
        max_results = self._max_results(ctx.config)
        data = self.http.get_json(self._api_url(target.account))
        if not isinstance(data, dict):
            raise ValueError("workable API returned unexpected payload (expected a JSON object)")

        company = (
            target.company or str(data.get("name") or "").strip() or _humanize_slug(target.account)
        )
        jobs = data.get("jobs")
        if jobs is None:
            jobs = []
        if not isinstance(jobs, list):
            raise ValueError(
                "workable API returned unexpected jobs payload (expected a JSON array)"
            )

        keywords = target.keywords.casefold()
        postings: list[JobPosting] = []
        for raw in jobs:
            posting = self._to_posting(raw, company=company)
            if posting is None:
                continue
            if keywords and keywords not in posting.title.casefold():
                continue
            postings.append(posting)
            if len(postings) >= max_results:
                break
        return postings

    @classmethod
    def _resolve(cls, ctx: ScrapeContext) -> _AccountTarget:
        account = str(ctx.config.get("account") or "").strip()
        if ctx.query_url:
            account = cls._account_from_url(ctx.query_url.strip()) or account
        account = cls._validate_account(account)
        company = str(ctx.config.get("company") or "").strip()
        return _AccountTarget(account=account, company=company, keywords=cls._keywords(ctx))

    @classmethod
    def _account_from_url(cls, query_url: str) -> str:
        parsed = urlparse(query_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("workable scraper query_url must be an http(s) careers or API URL")
        host = parsed.netloc.lower()
        if host != _APPLY_HOST:
            raise ValueError(
                "workable scraper query_url must be an apply.workable.com careers URL "
                "or widget API URL"
            )
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 5 and "/".join(parts[:4]) == "api/v1/widget/accounts":
            return parts[4]
        if parts and parts[0] not in _RESERVED_PATHS:
            return parts[0]
        raise ValueError("workable scraper could not determine account from query_url")

    @staticmethod
    def _validate_account(account: str) -> str:
        cleaned = account.strip()
        if not cleaned or not _ACCOUNT_RE.fullmatch(cleaned):
            raise ValueError(
                "workable scraper needs a query_url or config.account "
                "(alphanumeric account slug, optional internal hyphens)"
            )
        return cleaned

    @staticmethod
    def _api_url(account: str) -> str:
        return f"https://{_APPLY_HOST}{_WIDGET_PREFIX}{account}"

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
    def _to_posting(cls, raw: object, *, company: str) -> JobPosting | None:
        if not isinstance(raw, dict):
            return None
        external_id = str(raw.get("shortcode") or "").strip()
        title = str(raw.get("title") or "").strip()
        if not external_id or not title:
            return None
        url = str(raw.get("url") or raw.get("shortlink") or "").strip()
        if not url:
            url = f"https://{_APPLY_HOST}/j/{external_id}"
        return JobPosting(
            external_id=external_id,
            title=title,
            company=company,
            location=cls._location(raw),
            url=url,
            posted_at=cls._posted_at(raw),
            raw=raw,
        )

    @classmethod
    def _location(cls, raw: dict[str, Any]) -> str:
        locations = raw.get("locations")
        if isinstance(locations, list) and locations:
            parts = [cls._format_location_obj(item) for item in locations]
            joined = "; ".join(part for part in parts if part)
            if joined:
                return joined
        return cls._format_flat_location(raw)

    @staticmethod
    def _format_location_obj(value: object) -> str:
        if not isinstance(value, dict):
            return ""
        city = str(value.get("city") or "").strip()
        region = str(value.get("region") or value.get("state") or "").strip()
        country = str(value.get("country") or "").strip()
        bits = [bit for bit in (city, region, country) if bit]
        return ", ".join(bits)

    @staticmethod
    def _format_flat_location(raw: dict[str, Any]) -> str:
        city = str(raw.get("city") or "").strip()
        state = str(raw.get("state") or "").strip()
        country = str(raw.get("country") or "").strip()
        bits = [bit for bit in (city, state, country) if bit]
        return ", ".join(bits)

    @staticmethod
    def _posted_at(raw: dict[str, Any]) -> datetime | None:
        for key in ("published_on", "created_at"):
            value = raw.get(key)
            if not isinstance(value, str) or not value.strip():
                continue
            text = value.strip()
            try:
                if len(text) == 10 and text[4] == "-" and text[7] == "-":
                    return datetime(int(text[0:4]), int(text[5:7]), int(text[8:10]), tzinfo=UTC)
                return datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                continue
        return None


def _humanize_slug(slug: str) -> str:
    cleaned = slug.replace("-", " ").replace("_", " ").strip()
    return cleaned.title() if cleaned else slug
