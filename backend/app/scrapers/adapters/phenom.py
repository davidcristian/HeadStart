"""Phenom People careers-site adapter.

Phenom-backed employers expose a public search widget:

  GET  {careers_base_url}/{country}/{lang}/search-results  (CSRF + cookies)
  POST {careers_base_url}/widgets  (JSON, ddoKey=refineSearch)

Config / context:
  - ``query_url``: careers site root, locale path, or ``/widgets`` URL.
  - ``config["careers_base_url"]``: origin when ``query_url`` is empty.
  - ``config["company"]``: display name for postings.
  - ``config["country"]`` / ``config["locale"]``: Phenom path + payload
    (defaults ``us`` / ``en_us``). Locale ``en_global`` uses path lang ``en``.
  - ``config["ref_num"]``: optional tenant id; extracted from HTML when omitted.
  - ``config["keywords"]`` / ``q`` / ``search``: optional widget keyword filter.
  - ``config["selected_fields"]``: optional facet map ``{field: [values]}``.
  - ``config["page_size"]``: jobs per page (default 50, max 100).
  - ``config["max_results"]``: cap across pages (default 1000).

Use the canonical Phenom host (e.g. ``careers.cisco.com``), not vanity hosts
that 301 across domains, because CSRF cookies do not survive those redirects.
"""

from __future__ import annotations

from typing import Any

from app.scrapers.adapters.phenom_parse import (
    PhenomSearchTarget,
    extract_page,
    max_results,
    page_size,
    parse_session_html,
    resolve_target,
    search_results_url,
    to_posting,
)
from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext


@register_scraper("phenom")
class PhenomScraper(Scraper):
    """Fetch postings from a Phenom People public ``/widgets`` refineSearch API."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = resolve_target(ctx)
        size = page_size(ctx.config)
        limit = max_results(ctx.config)
        csrf, ref_num = self._init_session(target)
        if not target.ref_num and ref_num:
            target = PhenomSearchTarget(
                careers_base_url=target.careers_base_url,
                company=target.company,
                country=target.country,
                locale=target.locale,
                ref_num=ref_num,
                keywords=target.keywords,
                selected_fields=target.selected_fields,
            )

        postings: list[JobPosting] = []
        seen: set[str] = set()
        total: int | None = None
        offset = 0

        while len(postings) < limit:
            data = self._search(target, csrf=csrf, offset=offset, page_size=size)
            jobs, page_total = extract_page(data)
            if total is None:
                total = page_total
            if not jobs:
                break
            added = 0
            for raw in jobs:
                posting = to_posting(raw, target)
                if posting is None or posting.external_id in seen:
                    continue
                seen.add(posting.external_id)
                postings.append(posting)
                added += 1
                if len(postings) >= limit:
                    break
            offset += len(jobs)
            if added == 0 or len(jobs) < size:
                break
            if total is not None and offset >= total:
                break

        return postings

    def _init_session(self, target: PhenomSearchTarget) -> tuple[str | None, str]:
        """Seed cookies/CSRF and optionally discover ``refNum`` from HTML."""
        html = self.http.get_text(search_results_url(target))
        return parse_session_html(html)

    def _search(
        self,
        target: PhenomSearchTarget,
        *,
        csrf: str | None,
        offset: int,
        page_size: int,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "lang": target.locale,
            "deviceType": "desktop",
            "country": target.country,
            "pageName": "search-results",
            "ddoKey": "refineSearch",
            "from": offset,
            "size": page_size,
            "jobs": True,
            "counts": True,
            "all_fields": ["category", "country", "city", "type", "company"],
            "clearAll": False,
            "jdsource": "facets",
            "isSliderEnable": False,
            "pageId": "page20",
            "siteType": "external",
            "keywords": target.keywords,
            "global": True,
            "selected_fields": target.selected_fields,
            "sort": {"order": "desc", "field": "postedDate"},
            "locationData": {},
        }
        if target.ref_num:
            payload["refNum"] = target.ref_num
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": target.careers_base_url,
            "Referer": search_results_url(target),
        }
        if csrf:
            headers["x-csrf-token"] = csrf
        data = self.http.post_json(
            f"{target.careers_base_url}/widgets",
            json=payload,
            headers=headers,
        )
        if not isinstance(data, dict):
            raise ValueError("phenom API returned unexpected payload (expected a JSON object)")
        return data
