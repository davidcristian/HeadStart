from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.scrapers import ScrapeContext, get_scraper
from app.scrapers.playwright_browser import close_browser, get_browser


@pytest.fixture(autouse=True)
def _reset_browser_pool() -> None:
    close_browser()
    yield
    close_browser()


def _make_browser_mock() -> tuple[MagicMock, MagicMock, MagicMock]:
    page = MagicMock()
    browser = MagicMock()
    browser.new_page.return_value = page
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


def test_browser_pool_reuses_browser() -> None:
    browser, _, cm = _make_browser_mock()
    playwright = cm.__enter__.return_value
    with _patch_playwright(cm):
        first = get_browser()
        second = get_browser()
    assert first is second
    playwright.chromium.launch.assert_called_once()


def test_close_browser_shuts_down_playwright() -> None:
    browser, _, cm = _make_browser_mock()
    with _patch_playwright(cm):
        get_browser()
        close_browser()
    browser.close.assert_called_once()
    cm.__exit__.assert_called_once()


def test_playwright_extracts_items() -> None:
    browser, page, cm = _make_browser_mock()
    item_one = MagicMock()
    title_one = MagicMock()
    title_one.inner_text.return_value = "Backend Engineer"
    title_one.get_attribute.return_value = "/jobs/1"
    loc_one = MagicMock()
    loc_one.inner_text.return_value = "Amsterdam"
    item_one.query_selector.side_effect = lambda sel: {
        "a.title": title_one,
        "span.loc": loc_one,
    }.get(sel)

    item_two = MagicMock()
    title_two = MagicMock()
    title_two.inner_text.return_value = "Frontend Engineer"
    title_two.get_attribute.return_value = "https://x.test/jobs/2"
    loc_two = MagicMock()
    loc_two.inner_text.return_value = "Remote"
    item_two.query_selector.side_effect = lambda sel: {
        "a.title": title_two,
        "span.loc": loc_two,
    }.get(sel)

    page.query_selector_all.return_value = [item_one, item_two]

    with _patch_playwright(cm):
        scraper = get_scraper("playwright")
        ctx = ScrapeContext(
            query_url="https://x.test/careers",
            config={
                "item": "li.job",
                "title": "a.title",
                "url": "a.title",
                "location": "span.loc",
                "base_url": "https://x.test",
            },
        )
        postings = scraper.fetch(ctx)

    assert [p.title for p in postings] == ["Backend Engineer", "Frontend Engineer"]
    assert postings[0].url == "https://x.test/jobs/1"
    assert postings[1].url == "https://x.test/jobs/2"
    page.goto.assert_called_once_with(
        "https://x.test/careers",
        wait_until="networkidle",
        timeout=30_000,
    )
    page.route.assert_called_once()
    page.close.assert_called_once()


def test_playwright_retries_on_navigation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    browser, page, cm = _make_browser_mock()
    page.goto.side_effect = [RuntimeError("timeout"), None]
    page.query_selector_all.return_value = []

    sleeps: list[float] = []
    monkeypatch.setattr("app.scrapers.adapters.playwright_html.time.sleep", sleeps.append)

    with _patch_playwright(cm):
        scraper = get_scraper("playwright")
        ctx = ScrapeContext(
            query_url="https://x.test/careers",
            config={"item": "li.job", "max_retries": 1},
        )
        postings = scraper.fetch(ctx)

    assert postings == []
    assert page.goto.call_count == 2
    assert sleeps == [1.0]


def test_playwright_honors_config_overrides() -> None:
    browser, page, cm = _make_browser_mock()
    page.query_selector_all.return_value = []

    with _patch_playwright(cm):
        scraper = get_scraper("playwright")
        ctx = ScrapeContext(
            query_url="https://x.test/careers",
            config={
                "item": "li.job",
                "navigation_timeout_ms": 12_000,
                "wait_until": "domcontentloaded",
            },
        )
        scraper.fetch(ctx)

    page.goto.assert_called_once_with(
        "https://x.test/careers",
        wait_until="domcontentloaded",
        timeout=12_000,
    )
