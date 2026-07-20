"""Tests for the Rippling ATS scraper."""

from __future__ import annotations

import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client


def test_rippling_parses_and_merges_locations() -> None:
    fixture = load_fixture("rippling_jobs.json")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        assert str(request.url).endswith("/platform/api/ats/v1/board/rippling/jobs")
        return httpx.Response(200, text=fixture, headers={"content-type": "application/json"})

    scraper = get_scraper("rippling", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(config={"board": "rippling", "company": "Rippling"})
    )

    assert len(seen) == 1
    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "2f0674e6-f01f-4ecd-b459-e947241c211f"
    assert first.title == "Account Executive - Accountants Channel (East Coast)"
    assert first.company == "Rippling"
    assert first.location == "Remote (Connecticut, US); Remote (Massachusetts, US)"
    assert first.url.endswith("/rippling/jobs/2f0674e6-f01f-4ecd-b459-e947241c211f")
    assert postings[1].external_id == "94ac7084-9b63-4e9f-9e2a-fd5da349172d"
    assert first.content_hash() != postings[1].content_hash()


def test_rippling_accepts_ats_board_query_url() -> None:
    fixture = load_fixture("rippling_jobs.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("rippling", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(query_url="https://ats.rippling.com/petfolk/jobs")
    )

    assert seen["url"].endswith("/platform/api/ats/v1/board/petfolk/jobs")
    assert postings[0].company == "Petfolk"


def test_rippling_accepts_api_query_url() -> None:
    fixture = load_fixture("rippling_jobs.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("rippling", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://api.rippling.com/platform/api/ats/v1/board/acme/jobs",
            config={"company": "Acme"},
        )
    )
    assert seen["url"].endswith("/platform/api/ats/v1/board/acme/jobs")


def test_rippling_filters_keywords_from_config_and_filters() -> None:
    fixture = load_fixture("rippling_jobs.json")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("rippling", http=make_http_client(handler))
    by_config = scraper.fetch(
        ScrapeContext(config={"board": "rippling", "keywords": "Broker"})
    )
    assert len(by_config) == 1
    assert "Broker" in by_config[0].title

    by_filters = scraper.fetch(
        ScrapeContext(config={"board": "rippling"}, filters={"q": "Accountants"})
    )
    assert len(by_filters) == 1
    assert "Accountants" in by_filters[0].title


def test_rippling_rejects_missing_board() -> None:
    scraper = get_scraper("rippling", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="query_url or config.board"):
        scraper.fetch(ScrapeContext())


def test_rippling_rejects_invalid_board_slug() -> None:
    scraper = get_scraper("rippling", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="board"):
        scraper.fetch(ScrapeContext(config={"board": "../evil"}))


def test_rippling_rejects_non_http_query_url() -> None:
    scraper = get_scraper("rippling", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="http\\(s\\)"):
        scraper.fetch(ScrapeContext(query_url="ftp://ats.rippling.com/rippling/jobs"))


def test_rippling_rejects_unknown_host_query_url() -> None:
    scraper = get_scraper("rippling", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="ats.rippling.com"):
        scraper.fetch(ScrapeContext(query_url="https://example.com/rippling/jobs"))


def test_rippling_rejects_ats_url_without_board() -> None:
    scraper = get_scraper("rippling", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="could not determine board"):
        scraper.fetch(ScrapeContext(query_url="https://ats.rippling.com/"))


def test_rippling_rejects_malformed_api_path() -> None:
    scraper = get_scraper("rippling", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="could not determine board"):
        scraper.fetch(
            ScrapeContext(query_url="https://api.rippling.com/platform/api/ats/v1/jobs")
        )


def test_rippling_rejects_non_list_payload() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text='{"jobs": []}', headers={"content-type": "application/json"}
        )

    scraper = get_scraper("rippling", http=make_http_client(handler))
    with pytest.raises(ValueError, match="JSON array"):
        scraper.fetch(ScrapeContext(config={"board": "rippling"}))


def test_rippling_skips_invalid_rows_and_builds_url() -> None:
    payload = """
    [
      {"uuid": "1", "name": "A", "url": "https://ats.rippling.com/rippling/jobs/1",
       "workLocation": {"label": "Remote"}},
      "nope",
      {"uuid": "", "name": "Missing id"},
      {"uuid": "2", "name": "B", "workLocation": null},
      {"uuid": "2", "name": "B", "workLocation": "Austin, TX"},
      {"uuid": "3", "name": "C", "workLocation": {"id": "x"}}
    ]
    """

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=payload)

    scraper = get_scraper("rippling", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"board": "acme", "company": "Acme"}))
    assert len(postings) == 3
    assert postings[0].location == "Remote"
    assert postings[1].external_id == "2"
    assert postings[1].location == "Austin, TX"
    assert postings[1].url == "https://ats.rippling.com/acme/jobs/2"
    assert postings[2].location == ""


def test_rippling_respects_max_results_while_merging() -> None:
    payload = """
    [
      {"uuid": "1", "name": "A", "url": "https://ats.rippling.com/x/jobs/1",
       "workLocation": {"label": "NY"}},
      {"uuid": "2", "name": "B", "url": "https://ats.rippling.com/x/jobs/2",
       "workLocation": {"label": "SF"}},
      {"uuid": "1", "name": "A", "url": "https://ats.rippling.com/x/jobs/1",
       "workLocation": {"label": "Remote"}},
      {"uuid": "3", "name": "C", "url": "https://ats.rippling.com/x/jobs/3",
       "workLocation": {"label": "LA"}}
    ]
    """

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=payload)

    scraper = get_scraper("rippling", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(config={"board": "x", "company": "X", "max_results": 2})
    )
    assert len(postings) == 2
    assert postings[0].location == "NY; Remote"
    assert postings[1].external_id == "2"


def test_rippling_rejects_bad_max_results() -> None:
    scraper = get_scraper("rippling", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="max_results"):
        scraper.fetch(ScrapeContext(config={"board": "rippling", "max_results": 0}))


def test_rippling_rejects_non_numeric_max_results() -> None:
    scraper = get_scraper("rippling", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="max_results"):
        scraper.fetch(ScrapeContext(config={"board": "rippling", "max_results": "10"}))


def test_rippling_empty_board_returns_empty() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="[]", headers={"content-type": "application/json"})

    scraper = get_scraper("rippling", http=make_http_client(handler))
    assert scraper.fetch(ScrapeContext(config={"board": "bound"})) == []
