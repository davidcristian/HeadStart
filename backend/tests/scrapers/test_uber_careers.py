import json

import httpx

from app.scrapers import ScrapeContext, get_scraper
from app.scrapers.adapters.uber_careers_parse import (
    coerce_int64,
    format_location,
    parse_search_response,
)
from tests.conftest import load_fixture, make_http_client


def test_uber_careers_parses_postings() -> None:
    fixture = load_fixture("uber_careers_search.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "www.uber.com"
        assert request.url.path == "/api/loadSearchJobsResults"
        assert request.method == "POST"
        body = json.loads(request.content.decode())
        assert body["page"] == 0
        assert body["limit"] == 100
        return httpx.Response(200, json=json.loads(fixture))

    scraper = get_scraper("uber_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://www.uber.com/us/en/careers/list/",
            config={"company": "Uber"},
        )
    )

    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "154672"
    assert first.title == "Staff Software Engineer - Fulfillment Optimization"
    assert first.company == "Uber"
    assert "San Francisco" in first.location
    assert first.url == "https://www.uber.com/us/en/careers/list/154672"
    assert first.posted_at is not None
    assert postings[1].external_id == "160090"


def test_uber_careers_filters_keywords_client_side() -> None:
    fixture = load_fixture("uber_careers_search.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=json.loads(fixture))

    scraper = get_scraper("uber_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            config={"company": "Uber", "q": "account executive"},
        )
    )

    assert len(postings) == 1
    assert postings[0].title == "Senior Account Executive - Global Delivery Partnerships"


def test_uber_careers_sends_country_filter() -> None:
    fixture = load_fixture("uber_careers_search.json")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=json.loads(fixture))

    scraper = get_scraper("uber_careers", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(config={"company": "Uber", "country": "USA"}))

    body = captured["body"]
    assert isinstance(body, dict)
    params = body["params"]
    assert isinstance(params, dict)
    assert params["location"] == [{"country": "USA"}]


def test_format_location_handles_multi_city() -> None:
    location = format_location(
        [
            {"city": "San Francisco", "region": "California", "countryName": "United States"},
            {"city": "New York", "region": "New York", "countryName": "United States"},
        ]
    )
    assert location == "San Francisco, California, United States; New York, New York, United States"


def test_coerce_int64_reads_protobuf_shape() -> None:
    assert coerce_int64({"low": 498, "high": 0, "unsigned": False}) == 498
    assert coerce_int64(12) == 12


def test_parse_search_response_fixture() -> None:
    payload = json.loads(load_fixture("uber_careers_search.json"))
    postings, total = parse_search_response(
        payload,
        company="Uber",
        careers_base_url="https://www.uber.com/us/en/careers/list",
    )
    assert total == 2
    assert len(postings) == 2
