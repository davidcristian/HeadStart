"""SAP SuccessFactors Career Site Builder adapter.

SuccessFactors CSB employers expose a CSRF-gated public search API:

  GET  {careers_base_url}/
  POST {careers_base_url}/services/recruiting/v1/jobs

Hosts are typically ``{tenant}.jobs.hr.cloud.sap``. The homepage seeds
``JSESSIONID`` + ``X-CSRF-Token`` and lists category links under
``/go/<name>/<categoryId>/`` (prefer ``All-Jobs``).

Config / context:
  - ``query_url``: careers root or ``/services/recruiting/v1/jobs`` URL.
  - ``config["careers_base_url"]``: origin when ``query_url`` is empty.
  - ``config["company"]``: display name (defaults to humanized tenant slug).
  - ``config["locale"]``: apply URL locale segment (default ``en_US``).
  - ``config["category_id"]``: optional; otherwise discovered from homepage.
  - ``config["keywords"]`` / ``q`` / ``search``: client-side title filter
    (also sent in the JSON body for tenants that honor it).
  - ``config["max_results"]``: cap across pages (default 1000).
"""

from __future__ import annotations

from typing import Any

from app.scrapers.adapters.successfactors_parse import (
    SuccessFactorsTarget,
    extract_category_id,
    extract_csrf,
    extract_page,
    jobs_api_url,
    max_results,
    page_size,
    resolve_target,
    to_posting,
)
from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext


@register_scraper("successfactors")
class SuccessFactorsScraper(Scraper):
    """Fetch postings from a SuccessFactors Career Site Builder jobs API."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = resolve_target(ctx)
        limit = max_results(ctx.config)
        csrf, category_id = self._init_session(target)
        size = page_size()
        keywords = target.keywords.casefold()

        postings: list[JobPosting] = []
        seen: set[str] = set()
        total: int | None = None
        page = 0
        scanned = 0

        while len(postings) < limit:
            data = self._search(
                target,
                csrf=csrf,
                category_id=category_id,
                page_number=page,
            )
            jobs, page_total = extract_page(data)
            if total is None:
                total = page_total
            if not jobs:
                break
            scanned += len(jobs)
            for raw in jobs:
                posting = to_posting(raw, target)
                if posting is None or posting.external_id in seen:
                    continue
                if keywords and keywords not in posting.title.casefold():
                    continue
                seen.add(posting.external_id)
                postings.append(posting)
                if len(postings) >= limit:
                    break
            page += 1
            if len(jobs) < size:
                break
            if total is not None and scanned >= total:
                break

        return postings

    def _init_session(self, target: SuccessFactorsTarget) -> tuple[str, int]:
        """Seed cookies/CSRF and resolve the search category id."""
        html = self.http.get_text(f"{target.careers_base_url}/")
        csrf = extract_csrf(html)
        category_id = extract_category_id(html, preferred=target.category_id)
        return csrf, category_id

    def _search(
        self,
        target: SuccessFactorsTarget,
        *,
        csrf: str,
        category_id: int,
        page_number: int,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "locale": target.locale,
            "pageNumber": page_number,
            "sortBy": "",
            "keywords": target.keywords,
            "location": "",
            "facetFilters": {},
            "brand": "",
            "skills": [],
            "categoryId": category_id,
            "alertId": "",
            "rcmCandidateId": "",
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": target.careers_base_url,
            "Referer": f"{target.careers_base_url}/",
            "x-csrf-token": csrf,
        }
        data = self.http.post_json(
            jobs_api_url(target.careers_base_url),
            json=payload,
            headers=headers,
        )
        if not isinstance(data, dict):
            raise ValueError(
                "successfactors API returned unexpected payload (expected a JSON object)"
            )
        return data
