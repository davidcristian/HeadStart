import json
from typing import Any

import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from app.scrapers.adapters.google_careers import GoogleCareersScraper
from app.scrapers.adapters.google_careers_parse import parse_search_page
from tests.conftest import load_fixture, make_http_client


def _page(records: list[list[Any]]) -> str:
    """Build a Google search page whose init-data holds `records`."""
    blob = json.dumps([records])
    return f"AF_initDataCallback({{key: 'ds:1', hash: '1', data:{blob}}});"


def _record(external_id: str, title: str) -> list[Any]:
    return [external_id, title]


def test_google_careers_tolerates_malformed_json_blob() -> None:
    """A balanced-but-invalid embedded JSON blob must yield no postings, not crash."""
    html = "noise AF_initDataCallback({key: 'ds:1', data:[abc] });"
    postings = parse_search_page(
        html, company="Google", applications_base="https://careers.google.com", query_params={}
    )
    assert postings == []


def test_google_careers_parses_postings() -> None:
    fixture = load_fixture("google_careers_results.html")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/jobs/results/" in str(request.url)
        assert request.url.params.get("page") == "1"
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("google_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://www.google.com/about/careers/applications/jobs/results/?q=software",
            config={"company": "Google"},
        )
    )

    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "72271215732892358"
    assert first.title == "Software Engineer, Mobile (iOS), Google Photos"
    assert first.company == "Google"
    assert first.location == "Sydney NSW, Australia"
    assert (
        first.url == "https://www.google.com/about/careers/applications/jobs/results/"
        "72271215732892358-software-engineer-mobile-ios-google-photos?q=software"
    )
    assert first.posted_at is not None
    assert first.content_hash() != postings[1].content_hash()


def test_google_careers_builds_search_from_config() -> None:
    fixture = load_fixture("google_careers_results.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("google_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            config={"q": "software", "location": "United States", "company": "Google"},
        )
    )

    assert "q=software" in seen["url"]
    assert "location=United+States" in seen["url"]


def test_google_careers_reads_keyword_from_filters() -> None:
    fixture = load_fixture("google_careers_results.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("google_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            filters={"keywords_include": "platform"},
            config={"company": "Google"},
        )
    )

    assert "q=platform" in seen["url"]


def test_google_careers_paginates_until_short_page() -> None:
    fixture = load_fixture("google_careers_results.html")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url.params.get("page")))
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("google_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://www.google.com/about/careers/applications/jobs/results/?q=software",
            config={"company": "Google", "max_results": 50},
        )
    )

    assert len(postings) == 2
    assert calls == ["1"]


def test_google_careers_empty_page_stops() -> None:
    """A page with no records breaks immediately (line 57 path / not page_jobs)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_page([]))

    scraper = get_scraper("google_careers", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"q": "none", "company": "Google"}))
    assert postings == []


def test_google_careers_dedupes_across_pages_and_caps() -> None:
    """Duplicate ids skip (line 60), full pages paginate (line 67), max caps (line 64)."""
    page1 = [_record(str(i), f"Job {i}") for i in range(1, 21)]  # full page of 20
    page2 = [_record(str(i), f"Job {i}") for i in range(20, 26)]  # 20 is a duplicate

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page")
        return httpx.Response(200, text=_page(page1 if page == "1" else page2))

    scraper = get_scraper("google_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(config={"q": "software", "company": "Google", "max_results": 24})
    )
    # 20 from page1 + 4 new from page2 (dup "20" skipped, capped at 24)
    assert len(postings) == 24


def test_google_careers_full_page_fills_max_then_exits() -> None:
    """A full page reaching max_results re-checks the while and exits (47->69)."""
    page = [_record(str(i), f"Job {i}") for i in range(1, 21)]  # exactly 20

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_page(page))

    scraper = get_scraper("google_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(config={"q": "software", "company": "Google", "max_results": 20})
    )
    assert len(postings) == 20


def test_google_careers_requires_query_when_no_url() -> None:
    """No query_url and no keyword/location raises (line 94)."""
    scraper = get_scraper("google_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="needs a query_url or config"):
        scraper.fetch(ScrapeContext(config={"company": "Google"}))


def test_google_careers_rejects_non_google_url() -> None:
    """A non-google.com host raises (line 144)."""
    scraper = get_scraper("google_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="google.com careers URL"):
        scraper.fetch(ScrapeContext(query_url="https://example.com/jobs/results"))


def test_google_careers_url_injects_missing_keyword_and_location() -> None:
    """A results URL missing q/location gets them from config (lines 149, 151)."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=_page([]))

    scraper = get_scraper("google_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://www.google.com/about/careers/applications/jobs/results/",
            config={"q": "swe", "location": "Dublin", "company": "Google"},
        )
    )
    assert "q=swe" in seen["url"]
    assert "location=Dublin" in seen["url"]


def test_google_careers_careers_host_root_builds_search() -> None:
    """A careers.google.com root URL builds a fresh search URL (lines 154-155)."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=_page([]))

    scraper = get_scraper("google_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://careers.google.com/",
            config={"q": "swe", "company": "Google"},
        )
    )
    assert "/about/careers/applications/jobs/results/" in seen["url"]
    assert "q=swe" in seen["url"]


def test_google_careers_rejects_non_results_path() -> None:
    """A google.com URL that is not a /jobs/results page raises (line 156)."""
    scraper = get_scraper("google_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="must be a /jobs/results search page"):
        scraper.fetch(ScrapeContext(query_url="https://www.google.com/about/careers/applications/"))


@pytest.mark.parametrize("bad", ["nope", 0, -3, True])
def test_google_careers_max_results_validation(bad: object) -> None:
    """max_results must be a positive non-bool number (lines 178, 181)."""
    with pytest.raises(ValueError, match="max_results must be a positive integer"):
        GoogleCareersScraper._max_results({"max_results": bad})
