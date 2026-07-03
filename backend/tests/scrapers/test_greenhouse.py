import json

import httpx
import pytest

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


def test_greenhouse_builds_url_from_board_token() -> None:
    fixture = load_fixture("greenhouse_jobs.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("greenhouse", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(config={"board_token": "acme"}))

    assert seen["url"] == "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true"


def test_greenhouse_requires_query_url_or_board_token() -> None:
    scraper = get_scraper("greenhouse", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="query_url or config.board_token"):
        scraper.fetch(ScrapeContext(config={"company": "Other"}))


def test_greenhouse_handles_non_dict_location() -> None:
    payload = json.dumps(
        {"jobs": [{"id": 7, "title": "Eng", "absolute_url": "https://x/7", "location": None}]}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=payload, headers={"content-type": "application/json"})

    scraper = get_scraper("greenhouse", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"board_token": "acme"}))

    assert len(postings) == 1
    assert postings[0].location == ""
    assert postings[0].company == "acme"
