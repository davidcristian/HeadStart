"""Tests for the iCIMS / Jibe Attract scraper."""

from __future__ import annotations

import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client


def test_icims_parses_postings_with_pagination() -> None:
    page1 = load_fixture("icims_jobs_page1.json")
    page2 = load_fixture("icims_jobs_page2.json")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        assert "/api/jobs" in str(request.url)
        if "page=1" in str(request.url):
            return httpx.Response(200, text=page1, headers={"content-type": "application/json"})
        if "page=2" in str(request.url):
            return httpx.Response(200, text=page2, headers={"content-type": "application/json"})
        raise AssertionError(f"unexpected request: {request.url}")

    scraper = get_scraper("icims", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://careers.rivian.com/careers-home/jobs",
            config={"company": "Rivian", "page_size": 2},
        )
    )

    assert len(postings) == 3
    assert len(seen) == 2
    first = postings[0]
    assert first.external_id == "31370"
    assert first.title == "Sr. Supplier Development Engineer, Exteriors"
    assert first.company == "Rivian"
    assert first.location == "Normal, Illinois"
    assert first.url == "https://careers.rivian.com/jobs/31370"
    assert first.posted_at is not None
    assert postings[1].location == "Belgrade, Serbia"
    assert postings[2].title == "Sr. Product Manager, Global Financial Systems"
    assert first.content_hash() != postings[1].content_hash()


def test_icims_uses_careers_base_url_config() -> None:
    fixture = load_fixture("icims_jobs_page1.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("icims", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(config={"careers_base_url": "https://careers.costco.com"}))

    assert seen["url"].startswith("https://careers.costco.com/api/jobs?")
    assert "page=1" in seen["url"]
    assert "limit=50" in seen["url"]


def test_icims_sends_keywords_and_falls_back_to_hiring_org() -> None:
    fixture = load_fixture("icims_jobs_page1.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("icims", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://careers.rivian.com/api/jobs",
            config={"keywords": "software", "page_size": 2},
        )
    )

    assert "keywords=software" in seen["url"]
    assert postings[0].company == "Rivian"


def test_icims_keywords_from_filters() -> None:
    fixture = load_fixture("icims_jobs_page1.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("icims", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://careers.rivian.com/",
            filters={"keywords": "engineer"},
            config={"page_size": 2},
        )
    )

    assert "keywords=engineer" in seen["url"]


def test_icims_rejects_missing_base() -> None:
    scraper = get_scraper("icims", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="query_url or config.careers_base_url"):
        scraper.fetch(ScrapeContext())


def test_icims_rejects_non_http_query_url() -> None:
    scraper = get_scraper("icims", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="http\\(s\\)"):
        scraper.fetch(ScrapeContext(query_url="ftp://careers.rivian.com/jobs"))


def test_icims_rejects_non_dict_payload() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="[]", headers={"content-type": "application/json"})

    scraper = get_scraper("icims", http=make_http_client(handler))
    with pytest.raises(ValueError, match="JSON object"):
        scraper.fetch(ScrapeContext(query_url="https://careers.rivian.com/"))


def test_icims_rejects_non_list_jobs() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text='{"jobs": {}}', headers={"content-type": "application/json"}
        )

    scraper = get_scraper("icims", http=make_http_client(handler))
    with pytest.raises(ValueError, match="jobs field"):
        scraper.fetch(ScrapeContext(query_url="https://careers.rivian.com/"))


def test_icims_stops_on_empty_page() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text='{"totalCount": 0, "jobs": []}',
            headers={"content-type": "application/json"},
        )

    scraper = get_scraper("icims", http=make_http_client(handler))
    assert scraper.fetch(ScrapeContext(query_url="https://careers.rivian.com/")) == []


def test_icims_skips_invalid_and_duplicate_rows() -> None:
    payload = """
    {
      "totalCount": 4,
      "jobs": [
        {"data": {"slug": "1", "title": "A", "hiring_organization": "Acme", "full_location": "X"}},
        "nope",
        {"data": {"slug": "", "title": "Missing id"}},
        {"data": {"slug": "1", "title": "Dup", "hiring_organization": "Acme"}}
      ]
    }
    """

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=payload, headers={"content-type": "application/json"})

    scraper = get_scraper("icims", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(query_url="https://careers.rivian.com/"))
    assert len(postings) == 1
    assert postings[0].external_id == "1"


def test_icims_stops_when_max_results_reached() -> None:
    page1 = load_fixture("icims_jobs_page1.json")
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, text=page1)

    scraper = get_scraper("icims", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://careers.rivian.com/",
            config={"page_size": 2, "max_results": 1},
        )
    )
    assert len(postings) == 1
    assert calls["n"] == 1


def test_icims_rejects_bad_page_size() -> None:
    scraper = get_scraper("icims", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="page_size"):
        scraper.fetch(
            ScrapeContext(query_url="https://careers.rivian.com/", config={"page_size": 0})
        )


def test_icims_rejects_non_numeric_page_size() -> None:
    scraper = get_scraper("icims", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="page_size"):
        scraper.fetch(
            ScrapeContext(query_url="https://careers.rivian.com/", config={"page_size": "10"})
        )


def test_icims_rejects_bad_max_results() -> None:
    scraper = get_scraper("icims", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="max_results"):
        scraper.fetch(
            ScrapeContext(query_url="https://careers.rivian.com/", config={"max_results": True})
        )


def test_icims_rejects_non_positive_max_results() -> None:
    scraper = get_scraper("icims", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="max_results"):
        scraper.fetch(
            ScrapeContext(query_url="https://careers.rivian.com/", config={"max_results": 0})
        )


def test_icims_accepts_flat_job_rows_without_data_wrapper() -> None:
    payload = """
    {
      "totalCount": 1,
      "jobs": [{
        "slug": "42",
        "title": "Flat Role",
        "hiring_organization": "Acme",
        "full_location": "Remote"
      }]
    }
    """

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=payload)

    scraper = get_scraper("icims", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(query_url="https://careers.rivian.com/"))
    assert len(postings) == 1
    assert postings[0].external_id == "42"
    assert postings[0].title == "Flat Role"


def test_icims_builds_location_from_parts_and_tolerates_bad_date() -> None:
    payload = """
    {
      "totalCount": 1,
      "jobs": [{
        "data": {
          "slug": "9",
          "title": "Ops",
          "city": "Austin",
          "state": "Texas",
          "country": "United States",
          "posted_date": "not-a-date"
        }
      }]
    }
    """

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=payload)

    scraper = get_scraper("icims", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(query_url="https://careers.rivian.com/", config={"company": "Acme"})
    )
    assert postings[0].location == "Austin, Texas, United States"
    assert postings[0].posted_at is None
    assert postings[0].company == "Acme"
