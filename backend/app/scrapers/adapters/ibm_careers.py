"""IBM Careers public Falcon search adapter.

Post-acquisition HashiCorp (and other IBM brands) list roles on IBM Careers.
The marketing search UI is powered by a public JSON API:

  GET https://www-api.ibm.com/search/api/v1-1/ibmcom/appid/<appid>/responseFormat/json
      ?scope=<scope>&rmdt=ALL&appid=<appid>&query=<q>&nr=<n>&fr=<offset>&page=<p>

Config / context:
  - ``query_url``: ``ibm.com/careers/search?q=…``, ``careers.ibm.com``, or the
    API URL above.
  - ``config["keywords"]`` / ``query`` / ``q`` / ``search``: Falcon query
    (default ``*`` = all careers).
  - ``config["app_id"]`` / ``appid``: Falcon app id (default ``careers``).
  - ``config["scope"]``: Falcon scope (default ``careers2``).
  - ``config["company"]``: display name (default ``IBM``).
  - ``config["page_size"]`` / ``max_results``: pagination caps.
"""

from __future__ import annotations

from typing import Any

from app.scrapers.adapters.ibm_careers_parse import (
    IbmCareersTarget,
    extract_page,
    max_results,
    page_size,
    resolve_target,
    search_api_url,
    to_posting,
)
from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext


@register_scraper("ibm_careers")
class IbmCareersScraper(Scraper):
    """Fetch postings from IBM Careers via the public www-api Falcon search API."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = resolve_target(ctx)
        size = page_size(ctx.config)
        limit = max_results(ctx.config)

        postings: list[JobPosting] = []
        seen: set[str] = set()
        total: int | None = None
        offset = 0

        while len(postings) < limit:
            data = self._search(target, offset=offset, page_size=size)
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

    def _search(
        self,
        target: IbmCareersTarget,
        *,
        offset: int,
        page_size: int,
    ) -> dict[str, Any]:
        url = search_api_url(target, offset=offset, page_size=page_size)
        data = self.http.get_json(url)
        if not isinstance(data, dict):
            raise ValueError("ibm_careers API returned unexpected payload (expected a JSON object)")
        return data
