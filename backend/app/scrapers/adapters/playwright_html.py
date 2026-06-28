"""Playwright adapter for JS-heavy / anti-bot pages (opt-in).

Playwright is an optional dependency. Install with:
    pip install -e ".[playwright]" && playwright install chromium

Config mirrors `generic_html` (item/title/url/company/location selectors) but the
page is rendered in a headless browser before selectors are applied.
"""

from typing import Any
from urllib.parse import urljoin

from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext


@register_scraper("playwright")
class PlaywrightScraper(Scraper):
    """Render a page with a headless browser, then extract postings."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        if self._rate_limiter is not None:
            self._rate_limiter.wait()
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - exercised only without extra
            raise RuntimeError(
                "The 'playwright' adapter requires the optional dependency. "
                'Install with: pip install -e ".[playwright]" && playwright install chromium'
            ) from exc

        cfg = ctx.config
        item_sel = cfg.get("item")
        if not item_sel:
            raise ValueError("playwright scraper requires config.item (a CSS selector)")
        if not ctx.query_url:
            raise ValueError("playwright scraper requires a query_url")
        base_url = str(cfg.get("base_url") or ctx.query_url)

        postings: list[JobPosting] = []
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(ctx.query_url, wait_until="networkidle")
                for handle in page.query_selector_all(item_sel):
                    posting = self._parse(handle, cfg, base_url)
                    if posting is not None:
                        postings.append(posting)
            finally:
                browser.close()
        return postings

    @staticmethod
    def _parse(handle: Any, cfg: dict[str, Any], base_url: str) -> JobPosting | None:
        def text(selector: str | None) -> str:
            if not selector:
                return ""
            el = handle.query_selector(selector)
            return (el.inner_text().strip() if el else "") or ""

        def href(selector: str | None) -> str:
            el = handle.query_selector(selector) if selector else handle
            if el is None:
                return ""
            value = el.get_attribute("href")
            return urljoin(base_url, value) if value else ""

        title = text(cfg.get("title"))
        url = href(cfg.get("url"))
        if not title and not url:
            return None
        return JobPosting(
            external_id=url or title,
            title=title,
            company=text(cfg.get("company")),
            location=text(cfg.get("location")),
            url=url,
        )
