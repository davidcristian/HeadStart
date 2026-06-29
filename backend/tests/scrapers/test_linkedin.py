"""Tests for the LinkedIn job-search scraper."""

import httpx

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client

SEARCH_URL = "https://www.linkedin.com/jobs/search/?keywords=python&location=remote"
GUEST_API_PREFIX = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"


def test_linkedin_parses_guest_api_cards() -> None:
    fixture = load_fixture("linkedin_search.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("linkedin", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(query_url=SEARCH_URL))

    assert seen["url"].startswith(GUEST_API_PREFIX)
    assert "keywords=python" in seen["url"]
    assert "location=remote" in seen["url"]
    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "4432008529"
    assert first.title == "Python Developer"
    assert first.company == "CGI"
    assert first.location == "Halifax, Nova Scotia, Canada"
    assert first.url == "https://www.linkedin.com/jobs/view/python-developer-at-cgi-4432008529"
    assert first.posted_at is not None
    assert postings[1].company == "Open Systems Technologies"


def test_linkedin_builds_guest_api_from_config() -> None:
    fixture = load_fixture("linkedin_search.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("linkedin", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(config={"keywords": "python", "location": "remote"}))

    assert "keywords=python" in seen["url"]
    assert "location=remote" in seen["url"]


def test_linkedin_paginates_with_start_offset() -> None:
    page_one = load_fixture("linkedin_search_paged.html")
    page_two = load_fixture("linkedin_search_page2.html")
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        if "start=2" in str(request.url):
            return httpx.Response(200, text=page_two)
        return httpx.Response(200, text=page_one)

    scraper = get_scraper("linkedin", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(query_url=SEARCH_URL, config={"max_results": 3, "page_size": 2})
    )

    assert len(urls) == 2
    assert "start=2" in urls[1]
    assert len(postings) == 3
    assert postings[-1].title == "Data Engineer"


def test_linkedin_preserves_search_filters_from_query_url() -> None:
    fixture = load_fixture("linkedin_search.html")
    seen: dict[str, str] = {}
    search_url = (
        "https://www.linkedin.com/jobs/search/?keywords=python&location=remote"
        "&f_TPR=r604800&f_WT=2"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("linkedin", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(query_url=search_url))

    assert "f_TPR=r604800" in seen["url"]
    assert "f_WT=2" in seen["url"]


def test_linkedin_rejects_auth_wall() -> None:
    auth_html = "<html><title>Sign in to LinkedIn</title><div class='authwall'></div></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=auth_html)

    scraper = get_scraper("linkedin", http=make_http_client(handler))
    try:
        scraper.fetch(ScrapeContext(query_url=SEARCH_URL))
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "auth wall" in str(exc)
