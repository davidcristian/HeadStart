import httpx

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client


def test_microsoft_careers_parses_postings() -> None:
    fixture = load_fixture("microsoft_careers_search.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/api/pcsx/search" in str(request.url)
        assert request.url.params["domain"] == "microsoft.com"
        assert request.url.params["query"] == "software"
        assert request.url.params["start"] == "0"
        return httpx.Response(200, text=fixture, headers={"content-type": "application/json"})

    scraper = get_scraper("microsoft_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://apply.careers.microsoft.com/careers",
            config={"company": "Microsoft", "q": "software"},
        )
    )

    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "1970393556869024"
    assert first.title == "Software Engineer/Sr Software Engineer"
    assert first.company == "Microsoft"
    assert first.location == "Redmond, WA, US"
    assert first.url == "https://apply.careers.microsoft.com/careers/job/1970393556869024"
    assert first.posted_at is not None
    assert first.content_hash() != postings[1].content_hash()


def test_microsoft_careers_builds_search_from_config() -> None:
    fixture = load_fixture("microsoft_careers_search.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("microsoft_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            config={"q": "platform", "location": "Redmond", "company": "Microsoft"},
        )
    )

    assert "query=platform" in seen["url"]
    assert "location=Redmond" in seen["url"]


def test_microsoft_careers_reads_keyword_from_filters() -> None:
    fixture = load_fixture("microsoft_careers_search.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("microsoft_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            filters={"keywords_include": "kernel"},
            config={"company": "Microsoft"},
        )
    )

    assert "query=kernel" in seen["url"]


def test_microsoft_careers_paginates_until_short_page() -> None:
    fixture = load_fixture("microsoft_careers_search.json")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url.params.get("start")))
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("microsoft_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            config={"company": "Microsoft", "q": "software", "max_results": 50},
        )
    )

    assert len(postings) == 2
    assert calls == ["0"]
