"""Tests for the Indeed job-search scraper."""

import httpx

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client

SEARCH_URL = "https://www.indeed.com/jobs?q=python&l=remote"


def test_indeed_parses_mosaic_json() -> None:
    fixture = load_fixture("indeed_search.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("indeed", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(query_url=SEARCH_URL))

    assert seen["url"] == SEARCH_URL
    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "abc123def4567890"
    assert first.title == "Senior Python Developer"
    assert first.company == "Acme Corp"
    assert first.location == "Remote"
    assert first.url == "https://www.indeed.com/viewjob?jk=abc123def4567890"
    assert first.posted_at is not None
    assert postings[1].title == "Backend Engineer"


def test_indeed_builds_search_url_from_config() -> None:
    fixture = load_fixture("indeed_search.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("indeed", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(config={"q": "python", "l": "remote"}))

    assert seen["url"] == "https://www.indeed.com/jobs?q=python&l=remote&filter=0"


def test_indeed_paginates_with_start_offset() -> None:
    page_one = load_fixture("indeed_search_paged.html")
    page_two = load_fixture("indeed_search_page2.html")
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        if "start=10" in str(request.url):
            return httpx.Response(200, text=page_two)
        return httpx.Response(200, text=page_one)

    scraper = get_scraper("indeed", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(query_url=SEARCH_URL, config={"max_results": 3, "page_size": 10})
    )

    assert len(urls) == 2
    assert "start=10" in urls[1]
    assert len(postings) == 3
    assert postings[-1].title == "DevOps Engineer"


def test_indeed_falls_back_to_html_cards() -> None:
    fixture = load_fixture("indeed_search_cards.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("indeed", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(query_url=SEARCH_URL))

    assert len(postings) == 1
    assert postings[0].external_id == "htmljob00000001"
    assert postings[0].title == "Data Engineer"
    assert postings[0].company == "Gamma LLC"
    assert postings[0].location == "New York, NY"


def test_indeed_rejects_captcha_page() -> None:
    captcha_html = "<html><title>Security Check - Indeed.com</title></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=captcha_html)

    scraper = get_scraper("indeed", http=make_http_client(handler))
    try:
        scraper.fetch(ScrapeContext(query_url=SEARCH_URL))
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "Cloudflare" in str(exc)
