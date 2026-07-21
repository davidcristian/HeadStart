"""Tests for the Workable careers scraper."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client


def test_workable_parses_fixture_jobs() -> None:
    fixture = load_fixture("workable_jobs.json")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        assert str(request.url).endswith("/api/v1/widget/accounts/huggingface")
        return httpx.Response(200, text=fixture, headers={"content-type": "application/json"})

    scraper = get_scraper("workable", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(config={"account": "huggingface", "company": "Hugging Face"})
    )

    assert len(seen) == 1
    assert len(postings) == 3
    first = postings[0]
    assert first.external_id == "97904BAC90"
    assert first.title == "Data/Infrastructure Advocate Engineer - EMEA Remote"
    assert first.company == "Hugging Face"
    assert first.location == "Paris, Île-de-France, France"
    assert first.url == "https://apply.workable.com/j/97904BAC90"
    assert first.posted_at == datetime(2026, 5, 29, tzinfo=UTC)
    assert postings[1].location == (
        "New York, New York, United States; San Francisco, California, United States"
    )
    assert postings[2].external_id == "81B46579FE"
    assert first.content_hash() != postings[1].content_hash()


def test_workable_uses_widget_name_when_company_omitted() -> None:
    fixture = load_fixture("workable_jobs.json")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("workable", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"account": "huggingface"}))
    assert postings[0].company == "Hugging Face"


def test_workable_accepts_careers_query_url() -> None:
    fixture = load_fixture("workable_jobs.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("workable", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(query_url="https://apply.workable.com/acme/"))

    assert seen["url"].endswith("/api/v1/widget/accounts/acme")
    assert postings[0].company == "Hugging Face"


def test_workable_accepts_widget_api_query_url() -> None:
    fixture = load_fixture("workable_jobs.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("workable", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://apply.workable.com/api/v1/widget/accounts/acme",
            config={"company": "Acme"},
        )
    )
    assert seen["url"].endswith("/api/v1/widget/accounts/acme")


def test_workable_filters_keywords_from_config_and_filters() -> None:
    fixture = load_fixture("workable_jobs.json")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("workable", http=make_http_client(handler))
    by_config = scraper.fetch(
        ScrapeContext(config={"account": "huggingface", "keywords": "Machine Learning"})
    )
    assert len(by_config) == 1
    assert "Machine Learning" in by_config[0].title

    by_filters = scraper.fetch(
        ScrapeContext(config={"account": "huggingface"}, filters={"q": "Advocate"})
    )
    assert len(by_filters) == 2


def test_workable_rejects_missing_account() -> None:
    scraper = get_scraper("workable", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="query_url or config.account"):
        scraper.fetch(ScrapeContext())


def test_workable_rejects_invalid_account_slug() -> None:
    scraper = get_scraper("workable", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="account"):
        scraper.fetch(ScrapeContext(config={"account": "../evil"}))


def test_workable_rejects_non_http_query_url() -> None:
    scraper = get_scraper("workable", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="http\\(s\\)"):
        scraper.fetch(ScrapeContext(query_url="ftp://apply.workable.com/huggingface"))


def test_workable_rejects_unknown_host_query_url() -> None:
    scraper = get_scraper("workable", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="apply.workable.com"):
        scraper.fetch(ScrapeContext(query_url="https://example.com/huggingface"))


def test_workable_rejects_reserved_path_without_account() -> None:
    scraper = get_scraper("workable", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="could not determine account"):
        scraper.fetch(ScrapeContext(query_url="https://apply.workable.com/j/97904BAC90"))


def test_workable_rejects_malformed_api_path() -> None:
    scraper = get_scraper("workable", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="could not determine account"):
        scraper.fetch(ScrapeContext(query_url="https://apply.workable.com/api/v1/widget/"))


def test_workable_rejects_non_object_payload() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="[]", headers={"content-type": "application/json"})

    scraper = get_scraper("workable", http=make_http_client(handler))
    with pytest.raises(ValueError, match="JSON object"):
        scraper.fetch(ScrapeContext(config={"account": "huggingface"}))


def test_workable_rejects_non_list_jobs_payload() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text='{"name": "Acme", "jobs": {}}',
            headers={"content-type": "application/json"},
        )

    scraper = get_scraper("workable", http=make_http_client(handler))
    with pytest.raises(ValueError, match="jobs payload"):
        scraper.fetch(ScrapeContext(config={"account": "acme"}))


def test_workable_skips_invalid_rows_and_builds_url() -> None:
    payload = """
    {
      "name": "Acme",
      "jobs": [
        {"shortcode": "A1", "title": "Engineer", "city": "Austin", "state": "TX",
         "country": "United States"},
        "nope",
        {"shortcode": "", "title": "Missing id"},
        {"shortcode": "B2", "title": "Designer", "locations": [{"id": "x"}]},
        {"shortcode": "C3", "title": "PM", "locations": "bad",
         "published_on": "not-a-date", "created_at": "2026-01-02T03:04:05Z"}
      ]
    }
    """

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=payload)

    scraper = get_scraper("workable", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"account": "acme", "company": "Acme"}))
    assert len(postings) == 3
    assert postings[0].location == "Austin, TX, United States"
    assert postings[0].url == "https://apply.workable.com/j/A1"
    assert postings[1].external_id == "B2"
    assert postings[1].location == ""
    assert postings[2].posted_at == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def test_workable_respects_max_results() -> None:
    fixture = load_fixture("workable_jobs.json")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("workable", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(config={"account": "huggingface", "company": "HF", "max_results": 2})
    )
    assert len(postings) == 2


def test_workable_rejects_bad_max_results() -> None:
    scraper = get_scraper("workable", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="max_results"):
        scraper.fetch(ScrapeContext(config={"account": "huggingface", "max_results": 0}))


def test_workable_rejects_non_numeric_max_results() -> None:
    scraper = get_scraper("workable", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="max_results"):
        scraper.fetch(ScrapeContext(config={"account": "huggingface", "max_results": "10"}))


def test_workable_empty_jobs_returns_empty() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text='{"name": "Empty Co", "jobs": []}',
            headers={"content-type": "application/json"},
        )

    scraper = get_scraper("workable", http=make_http_client(handler))
    assert scraper.fetch(ScrapeContext(config={"account": "empty"})) == []


def test_workable_missing_jobs_key_returns_empty() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text='{"name": "Empty Co"}',
            headers={"content-type": "application/json"},
        )

    scraper = get_scraper("workable", http=make_http_client(handler))
    assert scraper.fetch(ScrapeContext(config={"account": "empty"})) == []


def test_workable_humanizes_company_when_widget_name_missing() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text='{"jobs": [{"shortcode": "X1", "title": "Role", "url": "https://apply.workable.com/j/X1"}]}',
            headers={"content-type": "application/json"},
        )

    scraper = get_scraper("workable", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"account": "acme-corp"}))
    assert postings[0].company == "Acme Corp"
