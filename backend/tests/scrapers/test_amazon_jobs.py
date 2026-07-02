import httpx

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client


def test_amazon_jobs_parses_postings() -> None:
    fixture = load_fixture("amazon_jobs_search.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/en/search.json" in str(request.url)
        assert request.url.params["base_query"] == "software"
        assert request.url.params["offset"] == "0"
        return httpx.Response(200, text=fixture, headers={"content-type": "application/json"})

    scraper = get_scraper("amazon_jobs", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://www.amazon.jobs/en/search?base_query=software",
            config={"company": "Amazon"},
        )
    )

    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "10410605"
    assert first.title == "Software Development Manager, Flight Software"
    assert first.company == "Amazon Kuiper Manufacturing Enterprises LLC"
    assert first.location == "Redmond, Washington, USA"
    assert (
        first.url
        == "https://www.amazon.jobs/en/jobs/10410605/software-development-manager-flight-software"
    )
    assert first.posted_at is not None
    assert first.content_hash() != postings[1].content_hash()


def test_amazon_jobs_builds_search_from_config() -> None:
    fixture = load_fixture("amazon_jobs_search.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("amazon_jobs", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            config={
                "q": "platform",
                "location": "Seattle",
                "country": "USA",
                "company": "Amazon",
            },
        )
    )

    assert "base_query=platform" in seen["url"]
    assert "loc_query=Seattle" in seen["url"]
    assert "country=USA" in seen["url"]


def test_amazon_jobs_reads_keyword_from_filters() -> None:
    fixture = load_fixture("amazon_jobs_search.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("amazon_jobs", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            filters={"keywords_include": "kernel"},
            config={"company": "Amazon"},
        )
    )

    assert "base_query=kernel" in seen["url"]


def test_amazon_jobs_paginates_until_short_page() -> None:
    fixture = load_fixture("amazon_jobs_search.json")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url.params.get("offset")))
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("amazon_jobs", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            config={"company": "Amazon", "q": "software", "max_results": 50},
        )
    )

    assert len(postings) == 2
    assert calls == ["0"]
