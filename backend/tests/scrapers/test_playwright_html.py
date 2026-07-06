"""Branch-coverage tests for the Playwright HTML adapter.

These complement ``test_playwright.py`` (which covers the browser pool and the
happy path) by exercising the validation guards, retry exhaustion, and the
per-item parse fallbacks. The browser is fully mocked; no real browser launches.
"""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.scrapers import ScrapeContext, get_scraper
from app.scrapers.playwright_browser import close_browser
from app.scrapers.rate_limit import RateLimiter


@pytest.fixture(autouse=True)
def _reset_browser_pool() -> None:
    close_browser()
    yield
    close_browser()


def _make_browser_mock() -> tuple[MagicMock, MagicMock, MagicMock]:
    page = MagicMock()
    context = MagicMock()
    context.new_page.return_value = page
    browser = MagicMock()
    browser.new_context.return_value = context
    playwright = MagicMock()
    playwright.chromium.launch.return_value = browser
    cm = MagicMock()
    cm.__enter__.return_value = playwright
    return browser, page, cm


def _patch_playwright(cm: MagicMock) -> Any:
    sync_playwright = MagicMock(return_value=cm)
    sync_api = MagicMock(sync_playwright=sync_playwright)
    return patch.dict(
        sys.modules,
        {
            "playwright": MagicMock(sync_api=sync_api),
            "playwright.sync_api": sync_api,
        },
    )


def test_playwright_invokes_rate_limiter() -> None:
    """A configured rate limiter is consulted before fetching."""
    browser, page, cm = _make_browser_mock()
    page.query_selector_all.return_value = []
    limiter = MagicMock(spec=RateLimiter)

    with _patch_playwright(cm):
        scraper = get_scraper("playwright", rate_limiter=limiter)
        scraper.fetch(ScrapeContext(query_url="https://x.test/careers", config={"item": "li.job"}))

    limiter.wait.assert_called_once_with()


def test_playwright_requires_item_selector() -> None:
    scraper = get_scraper("playwright")
    with pytest.raises(ValueError, match="requires config.item"):
        scraper.fetch(ScrapeContext(query_url="https://x.test/careers", config={}))


def test_playwright_requires_query_url() -> None:
    scraper = get_scraper("playwright")
    with pytest.raises(ValueError, match="requires a query_url"):
        scraper.fetch(ScrapeContext(config={"item": "li.job"}))


def test_playwright_raises_after_exhausting_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """When every attempt fails, the last exception propagates."""
    browser, page, cm = _make_browser_mock()
    page.goto.side_effect = RuntimeError("boom")

    sleeps: list[float] = []
    monkeypatch.setattr("app.scrapers.adapters.playwright_html.time.sleep", sleeps.append)

    with _patch_playwright(cm):
        scraper = get_scraper("playwright")
        with pytest.raises(RuntimeError, match="boom"):
            scraper.fetch(
                ScrapeContext(
                    query_url="https://x.test/careers",
                    config={"item": "li.job", "max_retries": 2},
                )
            )

    assert page.goto.call_count == 3
    assert sleeps == [1.0, 2.0]


def test_playwright_negative_max_retries_yields_empty() -> None:
    """A negative max_retries makes the attempt loop empty; fetch returns no postings."""
    browser, page, cm = _make_browser_mock()

    with _patch_playwright(cm):
        scraper = get_scraper("playwright")
        postings = scraper.fetch(
            ScrapeContext(
                query_url="https://x.test/careers",
                config={"item": "li.job", "max_retries": -1},
            )
        )

    assert postings == []
    page.goto.assert_not_called()


def test_playwright_skips_items_without_title_or_url() -> None:
    """An item element with neither a title nor a URL yields no posting."""
    browser, page, cm = _make_browser_mock()

    empty_item = MagicMock()
    empty_item.query_selector.return_value = None

    good_item = MagicMock()
    title = MagicMock()
    title.inner_text.return_value = "Engineer"
    title.get_attribute.return_value = "/jobs/1"
    good_item.query_selector.side_effect = lambda sel: {"a.title": title}.get(sel)

    page.query_selector_all.return_value = [empty_item, good_item]

    with _patch_playwright(cm):
        scraper = get_scraper("playwright")
        postings = scraper.fetch(
            ScrapeContext(
                query_url="https://x.test/careers",
                config={"item": "li.job", "title": "a.title", "url": "a.title"},
            )
        )

    assert [p.title for p in postings] == ["Engineer"]
    assert postings[0].url == "https://x.test/jobs/1"


def test_playwright_href_missing_element_returns_empty() -> None:
    """A url selector matching no element resolves the URL to an empty string."""
    browser, page, cm = _make_browser_mock()

    item = MagicMock()
    title = MagicMock()
    title.inner_text.return_value = "Titled"

    def _query(sel: str) -> Any:
        # title is present; the url selector matches nothing (href el is None).
        return title if sel == "span.title" else None

    item.query_selector.side_effect = _query
    page.query_selector_all.return_value = [item]

    with _patch_playwright(cm):
        scraper = get_scraper("playwright")
        postings = scraper.fetch(
            ScrapeContext(
                query_url="https://x.test/careers",
                config={"item": "li.job", "title": "span.title", "url": "a.missing"},
            )
        )

    assert postings[0].title == "Titled"
    assert postings[0].url == ""
    assert postings[0].external_id == "Titled"
