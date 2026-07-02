import httpx

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client


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
