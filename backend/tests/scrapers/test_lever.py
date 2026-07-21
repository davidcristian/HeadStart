import json

import httpx
import pytest

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


def test_lever_rejects_non_list_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jobs": []})

    scraper = get_scraper("lever", http=make_http_client(handler))
    with pytest.raises(ValueError, match="expected a JSON array"):
        scraper.fetch(ScrapeContext(config={"site": "acme"}))


def test_lever_requires_query_url_or_site() -> None:
    scraper = get_scraper("lever", http=make_http_client(lambda r: httpx.Response(200, json=[])))
    with pytest.raises(ValueError, match="query_url or config.site"):
        scraper.fetch(ScrapeContext(config={"company": "ACME"}))


def test_lever_jobs_page_url_without_slug_falls_back_to_config_site() -> None:
    fixture = load_fixture("lever_postings.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("lever", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(query_url="https://jobs.acme.lever.co/", config={"site": "acme"}))

    assert seen["url"] == "https://api.lever.co/v0/postings/acme?mode=json"


def test_lever_jobs_page_url_without_slug_or_site_raises() -> None:
    scraper = get_scraper("lever", http=make_http_client(lambda r: httpx.Response(200, json=[])))
    with pytest.raises(ValueError, match="could not determine site"):
        scraper.fetch(ScrapeContext(query_url="https://jobs.acme.lever.co/"))


def test_lever_preserves_existing_mode_param() -> None:
    fixture = load_fixture("lever_postings.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("lever", http=make_http_client(handler))
    url = "https://api.lever.co/v0/postings/other?mode=xml"
    scraper.fetch(ScrapeContext(query_url=url))

    assert "mode=xml" in seen["url"]
    assert "mode=json" not in seen["url"]


def test_lever_falls_back_to_all_locations_and_missing_fields() -> None:
    payload = json.dumps(
        [
            {
                "id": "job-1",
                "text": "Eng",
                "categories": {"allLocations": ["Berlin, DE"]},
            },
            {
                "id": "job-2",
                "text": "No categories",
                "categories": "not-a-dict",
            },
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=payload, headers={"content-type": "application/json"})

    scraper = get_scraper("lever", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"site": "acme"}))

    assert postings[0].location == "Berlin, DE"
    assert postings[0].posted_at is None
    assert postings[1].location == ""


def test_lever_empty_categories_and_empty_all_locations() -> None:
    payload = json.dumps(
        [{"id": "job-3", "text": "Eng", "categories": {"allLocations": []}, "createdAt": None}]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=payload, headers={"content-type": "application/json"})

    scraper = get_scraper("lever", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"site": "acme"}))

    assert postings[0].location == ""
    assert postings[0].posted_at is None


def test_lever_overflow_created_at_returns_none() -> None:
    """Out-of-range createdAt must not abort the scrape."""
    payload = json.dumps(
        [
            {
                "id": "job-overflow",
                "text": "Eng",
                "categories": {"location": "Remote"},
                "createdAt": 1e30,
                "hostedUrl": "https://jobs.lever.co/acme/job-overflow",
            },
            {
                "id": "job-ok",
                "text": "Eng 2",
                "categories": {"location": "Remote"},
                "createdAt": 1700000000000,
                "hostedUrl": "https://jobs.lever.co/acme/job-ok",
            },
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=payload, headers={"content-type": "application/json"})

    scraper = get_scraper("lever", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"site": "acme"}))

    assert len(postings) == 2
    assert postings[0].posted_at is None
    assert postings[1].posted_at is not None
