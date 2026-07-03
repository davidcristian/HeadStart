import json

import httpx

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client


def test_ashby_tolerates_malformed_published_date() -> None:
    """One unparseable date must not abort the whole scrape (posted_at falls to None)."""
    payload = json.dumps(
        {"jobs": [{"id": "1", "title": "Eng", "jobUrl": "https://x/1", "publishedAt": "nope"}]}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=payload, headers={"content-type": "application/json"})

    scraper = get_scraper("ashby", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"board": "acme"}))

    assert len(postings) == 1
    assert postings[0].posted_at is None


def test_ashby_parses_postings() -> None:
    fixture = load_fixture("ashby_postings.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "api.ashbyhq.com" in str(request.url)
        assert "/posting-api/job-board/acme" in str(request.url)
        return httpx.Response(200, text=fixture, headers={"content-type": "application/json"})

    scraper = get_scraper("ashby", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"board": "acme", "company": "ACME"}))

    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "7458d4e9-da2e-47bd-98cb-adfda43d42b2"
    assert first.title == "Engineering Manager, EU"
    assert first.company == "ACME"
    assert first.location == "Remote - European Union"
    assert first.url.endswith("7458d4e9-da2e-47bd-98cb-adfda43d42b2")
    assert first.posted_at is not None
    assert first.content_hash() != postings[1].content_hash()


def test_ashby_uses_secondary_location_when_primary_missing() -> None:
    fixture = load_fixture("ashby_postings.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("ashby", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"board": "acme"}))

    assert postings[1].location == "San Francisco, CA"


def test_ashby_uses_explicit_query_url() -> None:
    fixture = load_fixture("ashby_postings.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("ashby", http=make_http_client(handler))
    url = "https://api.ashbyhq.com/posting-api/job-board/other"
    scraper.fetch(ScrapeContext(query_url=url, config={"company": "Other"}))

    assert seen["url"] == url


def test_ashby_accepts_jobs_page_url() -> None:
    fixture = load_fixture("ashby_postings.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("ashby", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://jobs.ashbyhq.com/acme",
            config={"company": "ACME"},
        )
    )

    assert seen["url"] == "https://api.ashbyhq.com/posting-api/job-board/acme"


def test_ashby_include_compensation() -> None:
    fixture = load_fixture("ashby_postings.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("ashby", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(config={"board": "acme", "include_compensation": True}))

    assert "includeCompensation=true" in seen["url"]
