import httpx

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client


def test_greenhouse_parses_postings() -> None:
    fixture = load_fixture("greenhouse_jobs.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "boards-api.greenhouse.io" in str(request.url)
        return httpx.Response(200, text=fixture, headers={"content-type": "application/json"})

    scraper = get_scraper("greenhouse", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"board_token": "acme", "company": "ACME"}))

    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "5501001"
    assert first.title == "Senior Software Engineer"
    assert first.company == "ACME"
    assert first.location == "Amsterdam, Netherlands"
    assert first.url.endswith("/5501001")
    # Hash is stable and distinct between postings.
    assert first.content_hash() != postings[1].content_hash()


def test_greenhouse_uses_explicit_query_url() -> None:
    fixture = load_fixture("greenhouse_jobs.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("greenhouse", http=make_http_client(handler))
    url = "https://boards-api.greenhouse.io/v1/boards/other/jobs?content=true"
    scraper.fetch(ScrapeContext(query_url=url, config={"company": "Other"}))

    assert seen["url"] == url
