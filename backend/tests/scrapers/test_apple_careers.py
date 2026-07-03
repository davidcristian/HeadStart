import json
from typing import Any

import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from app.scrapers.adapters.apple_careers import AppleCareersScraper
from tests.conftest import load_fixture, make_http_client


def _search_html(jobs: list[dict], *, total: int | None = None) -> str:
    """Build an Apple search page whose hydration data holds `jobs`."""
    search: dict[str, Any] = {"searchResults": jobs}
    if total is not None:
        search["totalRecords"] = total
    data = {"loaderData": {"search": search}}
    escaped = json.dumps(data).replace("\\", "\\\\").replace('"', '\\"')
    return f'window.__staticRouterHydrationData = JSON.parse("{escaped}");'


def _job(req_id: str) -> dict:
    return {
        "reqId": req_id,
        "postingTitle": f"Job {req_id}",
        "transformedPostingTitle": f"job-{req_id}",
    }


def test_apple_careers_parses_postings() -> None:
    fixture = load_fixture("apple_careers_search.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("apple_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url=(
                "https://jobs.apple.com/en-us/search"
                "?search=software+engineer&location=united-states-USA"
            ),
            config={"company": "Apple"},
        )
    )

    assert "search=software+engineer" in seen["url"]
    assert "location=united-states-USA" in seen["url"]
    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "200670239-0836"
    assert first.title == "ML Research Engineer"
    assert first.company == "Apple"
    assert "Cupertino" in first.location
    assert first.url.startswith("https://jobs.apple.com/en-us/details/200670239-0836/")
    assert first.posted_at is not None
    assert first.content_hash() != postings[1].content_hash()


def test_apple_careers_builds_search_from_config() -> None:
    fixture = load_fixture("apple_careers_search.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("apple_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            config={
                "search": "platform",
                "location": "postLocation-USA",
                "locale": "en-us",
                "company": "Apple",
            },
        )
    )

    assert seen["url"] == (
        "https://jobs.apple.com/en-us/search?search=platform&location=postLocation-USA"
    )


def test_apple_careers_reads_keyword_from_filters() -> None:
    fixture = load_fixture("apple_careers_search.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("apple_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            filters={"keywords_include": "kernel"},
            config={"company": "Apple"},
        )
    )

    assert "search=kernel" in seen["url"]


def test_apple_careers_paginates_until_short_page() -> None:
    page1 = load_fixture("apple_careers_search_paginated_page1.html")
    page2 = load_fixture("apple_careers_search_page2.html")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "page=2" in str(request.url):
            return httpx.Response(200, text=page2)
        return httpx.Response(200, text=page1)

    scraper = get_scraper("apple_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            config={"company": "Apple", "search": "software", "max_results": 50},
        )
    )

    assert len(postings) == 4
    assert len(calls) == 2
    assert "page=2" in calls[1]


def test_apple_careers_empty_page_stops() -> None:
    """An empty results page breaks immediately (line 61)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_search_html([], total=0))

    scraper = get_scraper("apple_careers", http=make_http_client(handler))
    assert scraper.fetch(ScrapeContext(config={"search": "none"})) == []


def test_apple_careers_dedupes_and_caps_at_max_results() -> None:
    """Duplicate ids are skipped (line 65) and max_results caps the loop (line 69)."""
    jobs = [_job("1"), _job("1"), _job("2"), _job("3")]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_search_html(jobs, total=100))

    scraper = get_scraper("apple_careers", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"search": "x", "max_results": 2}))
    assert [p.external_id for p in postings] == ["1", "2"]


def test_apple_careers_all_duplicate_page_stops() -> None:
    """A second page that only repeats known ids breaks via before_count (line 71)."""
    page1 = [_job(str(i)) for i in range(1, 21)]  # full page of 20
    page2 = list(page1)  # identical ids -> nothing new

    def handler(request: httpx.Request) -> httpx.Response:
        if "page=2" in str(request.url):
            return httpx.Response(200, text=_search_html(page2, total=1000))
        return httpx.Response(200, text=_search_html(page1, total=1000))

    scraper = get_scraper("apple_careers", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"search": "x", "max_results": 500}))
    assert len(postings) == 20


def test_apple_careers_stops_when_total_reached() -> None:
    """When collected postings reach totalRecords, pagination stops (line 72)."""
    jobs = [_job("1"), _job("2")]  # totalRecords defaults to len -> 2

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_search_html(jobs))

    scraper = get_scraper("apple_careers", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"search": "x", "max_results": 500}))
    assert len(postings) == 2


def test_apple_careers_full_page_fills_max_then_exits() -> None:
    """A full page reaching max_results re-checks the while and exits (50->78)."""
    jobs = [_job(str(i)) for i in range(1, 21)]  # exactly one full page

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_search_html(jobs, total=1000))

    scraper = get_scraper("apple_careers", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"search": "x", "max_results": 20}))
    assert len(postings) == 20


def test_apple_careers_rejects_non_apple_url() -> None:
    """A non-jobs.apple.com host raises (line 91)."""
    scraper = get_scraper("apple_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="jobs.apple.com URL"):
        scraper.fetch(ScrapeContext(query_url="https://example.com/search"))


def test_apple_careers_url_without_locale_segment() -> None:
    """A URL with no locale segment leaves the default locale (93->95)."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=_search_html([]))

    scraper = get_scraper("apple_careers", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(query_url="https://jobs.apple.com/search?search=x"))
    assert "/en-us/search" in seen["url"]


def test_apple_careers_rejects_details_url() -> None:
    """A posting detail URL is rejected (line 96)."""
    scraper = get_scraper("apple_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="must be a search page"):
        scraper.fetch(ScrapeContext(query_url="https://jobs.apple.com/en-us/details/1/job"))


def test_apple_careers_url_builds_without_keyword() -> None:
    """A search URL with only a location omits the search param (106->108)."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=_search_html([]))

    scraper = get_scraper("apple_careers", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(config={"location": "united-states-USA"}))
    assert "search=" not in seen["url"]
    assert "location=united-states-USA" in seen["url"]


def test_apple_careers_first_param_skips_blank_then_uses_next() -> None:
    """A blank value for an earlier key falls through to a later key (144->142, then 145)."""
    params = {"search": [""], "q": ["real"]}
    assert AppleCareersScraper._first_param(params, ("search", "q"), "fb") == "real"


def test_apple_careers_first_param_returns_fallback() -> None:
    """No matching non-blank key returns the fallback (line 146)."""
    assert AppleCareersScraper._first_param({}, ("search", "q"), "fb") == "fb"


@pytest.mark.parametrize("bad", ["nope", 0, -1, True])
def test_apple_careers_max_results_validation(bad: object) -> None:
    """max_results must be a positive non-bool number (lines 152, 155)."""
    with pytest.raises(ValueError, match="max_results must be a positive integer"):
        AppleCareersScraper._max_results({"max_results": bad})
