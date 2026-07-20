"""Ashby job-board adapter.

Ashby exposes a public Postings API:
  https://api.ashbyhq.com/posting-api/job-board/<board>

Config / context:
  - `query_url`: full API URL, a jobs.ashbyhq.com board URL, or empty.
  - `config["board"]`: Ashby jobs page name (required when query_url is empty or a
    careers page URL).
  - `config["company"]`: display company name (defaults to board).
  - `config["include_compensation"]`: optional bool; adds salary data to the API
    response when true (default false).
"""

from urllib.parse import unquote, urlparse

from app.scrapers.adapters.ashby_parse import (
    api_url,
    parse_ashby_board_payload,
    with_compensation,
)
from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext


@register_scraper("ashby")
class AshbyScraper(Scraper):
    """Fetch postings from an Ashby public job board."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        url, company = self._resolve(ctx)
        data = self.http.get_json(url)
        if not isinstance(data, dict):
            raise ValueError("ashby API returned unexpected payload (expected a JSON object)")
        return parse_ashby_board_payload(data, company)

    def _resolve(self, ctx: ScrapeContext) -> tuple[str, str]:
        config = ctx.config
        board = str(config.get("board") or config.get("site") or "")
        company = str(config.get("company") or board or "")
        include_compensation = bool(config.get("include_compensation", False))

        if ctx.query_url:
            url = self._normalize_url(
                ctx.query_url,
                board=board,
                include_compensation=include_compensation,
            )
            return url, company

        if not board:
            raise ValueError("ashby scraper needs a query_url or config.board")
        return api_url(board, include_compensation), company

    @classmethod
    def _normalize_url(
        cls,
        query_url: str,
        *,
        board: str,
        include_compensation: bool,
    ) -> str:
        parsed = urlparse(query_url)
        host = parsed.netloc.lower()
        if host == "jobs.ashbyhq.com":
            slug = unquote(parsed.path.strip("/").split("/")[0] or board)
            if not slug:
                raise ValueError("ashby scraper could not determine board from query_url")
            return api_url(slug, include_compensation)
        if "posting-api/job-board" in parsed.path:
            return with_compensation(query_url, include_compensation)
        raise ValueError("ashby scraper query_url must be an API URL or jobs.ashbyhq.com board URL")
