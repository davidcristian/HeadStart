import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client


def test_snowflake_careers_parses_postings() -> None:
    fixture = load_fixture("snowflake_careers_postings.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.ashbyhq.com"
        assert request.url.path == "/posting-api/job-board/snowflake"
        return httpx.Response(200, text=fixture, headers={"content-type": "application/json"})

    scraper = get_scraper("snowflake_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://careers.snowflake.com/us/en/search-results",
            config={"company": "Snowflake"},
        )
    )

    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "00898e37-87aa-47e6-9df7-aefabac4ab01"
    assert first.title == "Senior Solution Engineer"
    assert first.company == "Snowflake"
    assert first.location == "US-NC-Remote"
    assert first.url.endswith("00898e37-87aa-47e6-9df7-aefabac4ab01")
    assert first.posted_at is not None
    assert postings[1].external_id == "15390ce2-d71d-44c7-bf55-e9d7cfcf11a5"


def test_snowflake_careers_filters_keywords_client_side() -> None:
    fixture = load_fixture("snowflake_careers_postings.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("snowflake_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            config={"company": "Snowflake", "q": "account executive"},
        )
    )

    assert len(postings) == 1
    assert postings[0].title == "Account Executive, Commercial"


def test_snowflake_careers_rejects_non_snowflake_host() -> None:
    scraper = get_scraper("snowflake_careers", http=make_http_client(lambda _: httpx.Response(200)))
    try:
        scraper.fetch(
            ScrapeContext(
                query_url="https://www.snowflake.com/en/careers",
                config={"company": "Snowflake"},
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "careers.snowflake.com" in str(exc)


def test_snowflake_careers_include_compensation() -> None:
    fixture = load_fixture("snowflake_careers_postings.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("snowflake_careers", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(config={"company": "Snowflake", "include_compensation": True}))

    assert "includeCompensation=true" in seen["url"]


def test_snowflake_careers_rejects_non_dict_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "an", "object"])

    scraper = get_scraper("snowflake_careers", http=make_http_client(handler))
    with pytest.raises(ValueError, match="unexpected payload"):
        scraper.fetch(ScrapeContext(config={"company": "Snowflake"}))


def test_snowflake_careers_rejects_non_search_path() -> None:
    scraper = get_scraper("snowflake_careers", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="careers search section"):
        scraper.fetch(
            ScrapeContext(
                query_url="https://careers.snowflake.com/some/other/page",
                config={"company": "Snowflake"},
            )
        )


def test_snowflake_careers_keyword_from_filters() -> None:
    """When no config keyword is set, the filters keyword drives client-side filtering."""
    fixture = load_fixture("snowflake_careers_postings.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("snowflake_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            config={"company": "Snowflake"},
            filters={"keywords_include": "account executive"},
        )
    )
    assert len(postings) == 1
    assert postings[0].title == "Account Executive, Commercial"
