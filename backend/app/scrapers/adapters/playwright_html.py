"""Playwright adapter for JS-heavy / anti-bot pages (opt-in).

Playwright is an optional dependency. Install with:
    pip install -e ".[playwright]" && playwright install chromium

Config mirrors `generic_html` (item/title/url/company/location selectors) but the
page is rendered in a headless browser before selectors are applied.

Production workers use a process-scoped browser pool (see `playwright_browser`).
Per-source overrides: `navigation_timeout_ms`, `wait_until`, `max_retries`.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urljoin

from app.core.config import settings
from app.scrapers.base import Scraper, register_scraper
from app.scrapers.playwright_browser import get_browser
from app.scrapers.playwright_outbound import install_playwright_outbound_guard
from app.scrapers.types import JobPosting, ScrapeContext


@register_scraper("playwright")
class PlaywrightScraper(Scraper):
    """Render a page with a headless browser, then extract postings."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        if self._rate_limiter is not None:
            self._rate_limiter.wait()

        cfg = ctx.config
        item_sel = cfg.get("item")
        if not item_sel:
            raise ValueError("playwright scraper requires config.item (a CSS selector)")
        if not ctx.query_url:
            raise ValueError("playwright scraper requires a query_url")

        timeout_ms = int(
            cfg.get("navigation_timeout_ms", settings.playwright_navigation_timeout_ms)
        )
        wait_until = str(cfg.get("wait_until", "networkidle"))
        max_retries_raw = cfg.get("max_retries")
        max_retries = (
            int(max_retries_raw) if max_retries_raw is not None else settings.playwright_max_retries
        )

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                return self._fetch_once(ctx, item_sel, timeout_ms, wait_until)
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    delay = min(2**attempt, 8)
                    time.sleep(delay)
                    continue
                raise
        if last_exc is not None:
            raise last_exc
        return []

    def _fetch_once(
        self,
        ctx: ScrapeContext,
        item_sel: str,
        timeout_ms: int,
        wait_until: str,
    ) -> list[JobPosting]:
        cfg = ctx.config
        base_url = str(cfg.get("base_url") or ctx.query_url)

        postings: list[JobPosting] = []
        browser = get_browser()
        page = browser.new_page()
        assert_outbound = install_playwright_outbound_guard(page)
        try:
            page.goto(ctx.query_url, wait_until=wait_until, timeout=timeout_ms)
            assert_outbound()
            for handle in page.query_selector_all(item_sel):
                posting = self._parse(handle, cfg, base_url)
                if posting is not None:
                    postings.append(posting)
        finally:
            page.close()
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
