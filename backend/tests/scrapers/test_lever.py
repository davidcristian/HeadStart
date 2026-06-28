import httpx

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client


def test_lever_parses_postings() -> None:
    fixture = load_fixture("lever_postings.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "api.lever.co" in str(request.url)
        assert "mode=json" in str(request.url)
        return httpx.Response(200, text=fixture, headers={"content-type": "application/json"})

    scraper = get_scraper("lever", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"site": "acme", "company": "ACME"}))

    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "33538a2f-d27d-4a96-8f05-fa4b0e4d940e"
    assert first.title == "Senior Software Engineer"
    assert first.company == "ACME"
    assert first.location == "Amsterdam, Netherlands"
    assert first.url.endswith("33538a2f-d27d-4a96-8f05-fa4b0e4d940e")
    assert first.posted_at is not None
    assert first.content_hash() != postings[1].content_hash()


def test_lever_uses_explicit_query_url() -> None:
    fixture = load_fixture("lever_postings.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("lever", http=make_http_client(handler))
    url = "https://api.lever.co/v0/postings/other"
    scraper.fetch(ScrapeContext(query_url=url, config={"company": "Other"}))

    assert seen["url"] == f"{url}?mode=json"


def test_lever_accepts_jobs_page_url() -> None:
    fixture = load_fixture("lever_postings.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("lever", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://jobs.lever.co/acme",
            config={"company": "ACME"},
        )
    )

    assert seen["url"] == "https://api.lever.co/v0/postings/acme?mode=json"


def test_lever_eu_region() -> None:
    fixture = load_fixture("lever_postings.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("lever", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(config={"site": "acme", "region": "eu"}))

    assert seen["url"] == "https://api.eu.lever.co/v0/postings/acme?mode=json"
