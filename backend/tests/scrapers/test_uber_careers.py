import json

import httpx
import pytest

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


def _page(job_ids: list[int], total: int) -> dict[str, object]:
    return {
        "status": "success",
        "data": {
            "totalResults": {"low": total, "high": 0, "unsigned": False},
            "results": [{"id": jid, "title": f"Job {jid}"} for jid in job_ids],
        },
    }


def test_uber_careers_rejects_non_dict_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "a", "dict"])

    scraper = get_scraper("uber_careers", http=make_http_client(handler))
    with pytest.raises(ValueError, match="expected a JSON object"):
        scraper.fetch(ScrapeContext(config={"company": "Uber"}))


def test_uber_careers_stops_on_empty_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_page([], total=10))

    scraper = get_scraper("uber_careers", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"company": "Uber"}))
    assert postings == []


def test_uber_careers_skips_duplicate_ids_across_pages() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        calls.append(body["page"])
        if body["page"] == 0:
            return httpx.Response(200, json=_page([1, 2], total=4))
        return httpx.Response(200, json=_page([2, 3], total=4))

    scraper = get_scraper("uber_careers", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"company": "Uber", "page_size": 2}))
    ids = {p.external_id for p in postings}
    assert ids == {"1", "2", "3"}
    assert calls == [0, 1]


def test_uber_careers_stops_when_max_results_reached_mid_page() -> None:
    # max_results is hit inside the for-loop (line 80 break); the page/total
    # guards do not fire, so the while condition is re-checked and is now false,
    # exercising the loop-exit path (53->87).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_page([1, 2, 3, 4, 5], total=100))

    scraper = get_scraper("uber_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(config={"company": "Uber", "page_size": 5, "max_results": 2})
    )
    assert len(postings) == 2


def test_uber_careers_stops_when_page_reaches_total() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        calls.append(body["page"])
        return httpx.Response(200, json=_page([1, 2], total=2))

    scraper = get_scraper("uber_careers", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"company": "Uber", "page_size": 2}))
    assert len(postings) == 2
    assert calls == [0]


def test_uber_careers_stops_on_short_page() -> None:
    # total larger than what the API actually returns; a short page ends it.
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        calls.append(body["page"])
        return httpx.Response(200, json=_page([1], total=100))

    scraper = get_scraper("uber_careers", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"company": "Uber", "page_size": 2}))
    assert len(postings) == 1
    assert calls == [0]


def test_uber_careers_rejects_non_uber_host() -> None:
    scraper = get_scraper("uber_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="requires an uber.com careers URL"):
        scraper.fetch(ScrapeContext(query_url="https://example.com/careers/list"))


def test_uber_careers_rejects_non_careers_path() -> None:
    scraper = get_scraper("uber_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="must point at the careers section"):
        scraper.fetch(ScrapeContext(query_url="https://www.uber.com/about"))


def test_uber_careers_query_url_without_locale_prefix() -> None:
    # /careers path with no 2-letter locale segments -> keeps default locale path.
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["referer"] = request.headers.get("referer", "")
        return httpx.Response(200, json=_page([1], total=1))

    scraper = get_scraper("uber_careers", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(query_url="https://www.uber.com/careers/list/"))
    assert "/us/en/careers/list/" in seen["referer"]


def test_uber_careers_keyword_from_filters() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_page([], total=0))

    scraper = get_scraper("uber_careers", http=make_http_client(handler))
    # No matching jobs so result is empty, but this exercises the filters path.
    postings = scraper.fetch(
        ScrapeContext(config={"company": "Uber"}, filters={"keywords_include": "nomatch"})
    )
    assert postings == []


def test_uber_careers_country_from_filters_location() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=_page([1], total=1))

    scraper = get_scraper("uber_careers", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(config={"company": "Uber"}, filters={"location": "germany"}))
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["params"]["location"] == [{"country": "GERMANY"}]


def test_uber_careers_rejects_bad_page_size() -> None:
    scraper = get_scraper("uber_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="page_size must be a positive integer"):
        scraper.fetch(ScrapeContext(config={"page_size": "big"}))


def test_uber_careers_rejects_non_positive_page_size() -> None:
    scraper = get_scraper("uber_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="page_size must be a positive integer"):
        scraper.fetch(ScrapeContext(config={"page_size": 0}))


def test_uber_careers_rejects_bad_max_results() -> None:
    scraper = get_scraper("uber_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="max_results must be a positive integer"):
        scraper.fetch(ScrapeContext(config={"max_results": "big"}))


def test_uber_careers_rejects_non_positive_max_results() -> None:
    scraper = get_scraper("uber_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="max_results must be a positive integer"):
        scraper.fetch(ScrapeContext(config={"max_results": 0}))
