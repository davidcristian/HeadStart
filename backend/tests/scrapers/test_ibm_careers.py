"""Tests for the IBM Careers Falcon search scraper."""

from __future__ import annotations

import json

import httpx
import pytest

from app.portals.catalog import CURATED_PORTALS, get_portal_preset
from app.scrapers import ScrapeContext, get_scraper
from app.scrapers.adapters.ibm_careers_parse import (
    extract_page,
    page_size,
    search_api_url,
    to_posting,
)
from app.scrapers.adapters.ibm_careers_parse import (
    IbmCareersTarget,
    resolve_target,
)
from app.scrapers.url_detect import detect_source_from_url
from tests.conftest import load_fixture, make_http_client


def test_ibm_careers_parses_hashicorp_hits() -> None:
    fixture = load_fixture("ibm_careers_page1.json")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        assert "www-api.ibm.com" in str(request.url)
        assert "appid=careers" in str(request.url)
        assert "scope=careers2" in str(request.url)
        assert "query=HashiCorp" in str(request.url)
        return httpx.Response(200, text=fixture, headers={"content-type": "application/json"})

    scraper = get_scraper("ibm_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(config={"keywords": "HashiCorp", "company": "HashiCorp"})
    )

    assert len(seen) == 1
    assert len(postings) == 3
    first = next(p for p in postings if p.external_id == "116932")
    assert first.title == "Field CTO HashiCorp"
    assert first.company == "HashiCorp"
    assert first.location == "Boston, US"
    assert "jobId=116932" in first.url
    assert first.posted_at is not None


def test_ibm_careers_paginates_until_empty() -> None:
    page1 = {
        "resultset": {
            "searchresults": {
                "totalresults": 3,
                "searchresultlist": [
                    {
                        "title": "Role A",
                        "id": "a",
                        "url": "https://careers.ibm.com/careers/JobDetail?jobId=1",
                        "docattributes": [{"field_text_01": "1"}],
                    },
                    {
                        "title": "Role B",
                        "id": "b",
                        "url": "https://careers.ibm.com/careers/JobDetail?jobId=2",
                        "docattributes": [{"field_text_01": "2"}],
                    },
                ],
            }
        }
    }
    page2 = {
        "resultset": {
            "searchresults": {
                "totalresults": 3,
                "searchresultlist": [
                    {
                        "title": "Role C",
                        "id": "c",
                        "url": "https://careers.ibm.com/careers/JobDetail?jobId=3",
                        "docattributes": [{"field_text_01": "3"}],
                    },
                ],
            }
        }
    }
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        if "fr=0" in str(request.url):
            return httpx.Response(200, json=page1)
        return httpx.Response(200, json=page2)

    scraper = get_scraper("ibm_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(config={"keywords": "HashiCorp", "company": "HashiCorp", "page_size": 2})
    )
    assert [p.external_id for p in postings] == ["1", "2", "3"]
    assert any("fr=2" in url for url in urls)


def test_ibm_careers_accepts_careers_search_query_url() -> None:
    fixture = load_fixture("ibm_careers_page1.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("ibm_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://www.ibm.com/careers/search?q=HashiCorp",
            config={"company": "HashiCorp"},
        )
    )
    assert "query=HashiCorp" in seen["url"]
    assert postings[0].company == "HashiCorp"


def test_ibm_careers_accepts_api_query_url() -> None:
    fixture = load_fixture("ibm_careers_page1.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("ibm_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url=(
                "https://www-api.ibm.com/search/api/v1-1/ibmcom/appid/careers/"
                "responseFormat/json?scope=careers2&query=Vault"
            ),
            config={"company": "IBM"},
        )
    )
    assert "query=Vault" in seen["url"]


def test_ibm_careers_rejects_non_ibm_query_url() -> None:
    scraper = get_scraper("ibm_careers", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="IBM careers"):
        scraper.fetch(ScrapeContext(query_url="https://example.com/jobs"))


def test_ibm_careers_rejects_non_http_query_url() -> None:
    scraper = get_scraper("ibm_careers", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="http"):
        scraper.fetch(ScrapeContext(query_url="ftp://www.ibm.com/careers/search"))


def test_ibm_careers_rejects_non_object_payload() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="[]", headers={"content-type": "application/json"})

    scraper = get_scraper("ibm_careers", http=make_http_client(handler))
    with pytest.raises(ValueError, match="unexpected payload"):
        scraper.fetch(ScrapeContext(config={"keywords": "HashiCorp"}))


def test_ibm_careers_skips_malformed_hits() -> None:
    payload = {
        "resultset": {
            "searchresults": {
                "totalresults": 2,
                "searchresultlist": [
                    {"title": "", "id": "x"},
                    {
                        "title": "Good Role",
                        "id": "abc",
                        "url": "https://careers.ibm.com/careers/JobDetail?jobId=1",
                        "docattributes": [{"field_text_01": "1"}, {"field_keyword_19": "Remote"}],
                    },
                    {"title": "No Id"},
                ],
            }
        }
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    scraper = get_scraper("ibm_careers", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"company": "IBM"}))
    assert len(postings) == 1
    assert postings[0].external_id == "1"
    assert postings[0].location == "Remote"


def test_ibm_careers_extract_page_handles_bad_shapes() -> None:
    assert extract_page(None) == ([], None)
    assert extract_page({}) == ([], None)
    assert extract_page({"resultset": []}) == ([], None)
    assert extract_page({"resultset": {"searchresults": []}}) == ([], None)
    hits, total = extract_page(
        {"resultset": {"searchresults": {"totalresults": 3, "searchresultlist": {"title": "x"}}}}
    )
    assert total == 3
    assert len(hits) == 1
    assert extract_page(
        {"resultset": {"searchresults": {"totalresults": True, "searchresultlist": []}}}
    ) == ([], None)


def test_ibm_careers_page_size_clamps() -> None:
    assert page_size({}) == 50
    assert page_size({"page_size": 0}) == 50
    assert page_size({"page_size": 500}) == 100


def test_ibm_careers_to_posting_builds_url_from_job_id() -> None:
    target = IbmCareersTarget(
        app_id="careers", scope="careers2", query="HashiCorp", company="HashiCorp"
    )
    posting = to_posting(
        {
            "title": "Engineer",
            "docattributes": [{"field_text_01": "42"}],
        },
        target,
    )
    assert posting is not None
    assert posting.url.endswith("jobId=42")


def test_ibm_careers_search_api_url_encodes_query() -> None:
    target = IbmCareersTarget(
        app_id="careers", scope="careers2", query="Hashi Corp", company="IBM"
    )
    url = search_api_url(target, offset=50, page_size=25)
    assert "fr=50" in url
    assert "nr=25" in url
    assert "page=3" in url
    assert "query=Hashi+Corp" in url or "query=Hashi%20Corp" in url


def test_ibm_careers_resolve_defaults_to_wildcard_query() -> None:
    target = resolve_target(ScrapeContext(config={"company": "IBM"}))
    assert target.query == "*"
    assert target.app_id == "careers"
    assert target.scope == "careers2"


def test_detect_ibm_careers_from_marketing_search() -> None:
    detected = detect_source_from_url("https://www.ibm.com/careers/search?q=HashiCorp")
    assert detected is not None
    assert detected.adapter_key == "ibm_careers"
    assert detected.default_config["keywords"] == "HashiCorp"
    assert detected.default_config["app_id"] == "careers"


def test_detect_ibm_careers_from_api_url() -> None:
    detected = detect_source_from_url(
        "https://www-api.ibm.com/search/api/v1-1/ibmcom/appid/careers/"
        "responseFormat/json?scope=careers2&query=HashiCorp"
    )
    assert detected is not None
    assert detected.adapter_key == "ibm_careers"
    assert detected.default_config["keywords"] == "HashiCorp"


def test_detect_ibm_careers_ignores_unrelated_ibm_paths() -> None:
    assert detect_source_from_url("https://www.ibm.com/products") is None


def test_ibm_careers_stops_on_empty_first_page() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"resultset": {"searchresults": {"totalresults": 0, "searchresultlist": []}}},
        )

    scraper = get_scraper("ibm_careers", http=make_http_client(handler))
    assert scraper.fetch(ScrapeContext(config={"keywords": "Nope"})) == []


def test_ibm_careers_respects_max_results_and_skips_duplicates() -> None:
    payload = {
        "resultset": {
            "searchresults": {
                "totalresults": 5,
                "searchresultlist": [
                    {
                        "title": "One",
                        "id": "a",
                        "docattributes": [{"field_text_01": "1"}],
                        "url": "https://careers.ibm.com/careers/JobDetail?jobId=1",
                    },
                    {
                        "title": "Dup",
                        "id": "a2",
                        "docattributes": [{"field_text_01": "1"}],
                        "url": "https://careers.ibm.com/careers/JobDetail?jobId=1",
                    },
                    {
                        "title": "Two",
                        "id": "b",
                        "docattributes": [{"field_text_01": "2"}],
                        "url": "https://careers.ibm.com/careers/JobDetail?jobId=2",
                    },
                    {
                        "title": "Three",
                        "id": "c",
                        "docattributes": [{"field_text_01": "3"}],
                        "url": "https://careers.ibm.com/careers/JobDetail?jobId=3",
                    },
                ],
            }
        }
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    scraper = get_scraper("ibm_careers", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"max_results": 2, "page_size": 10}))
    assert [p.external_id for p in postings] == ["1", "2"]


def test_ibm_careers_keywords_from_filters_and_careers_host() -> None:
    fixture = load_fixture("ibm_careers_page1.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("ibm_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://careers.ibm.com/en_US/careers/SearchJobs",
            filters={"q": "Terraform"},
        )
    )
    assert "query=Terraform" in seen["url"]


def test_ibm_careers_max_results_and_page_size_defaults() -> None:
    from app.scrapers.adapters.ibm_careers_parse import max_results as mr

    assert mr({}) == 1000
    assert mr({"max_results": 0}) == 1000
    assert mr({"max_results": 9999}) == 2000


def test_ibm_careers_extract_page_non_list_hits() -> None:
    assert extract_page(
        {"resultset": {"searchresults": {"totalresults": 1, "searchresultlist": "x"}}}
    ) == ([], 1)


def test_ibm_careers_posted_at_date_only_and_iso() -> None:
    target = IbmCareersTarget(
        app_id="careers", scope="careers2", query="*", company="IBM"
    )
    with_date = to_posting(
        {
            "title": "A",
            "id": "x",
            "docattributes": [
                {},
                {"field_text_01": "9"},
                {"dcdate": "2026-01-02"},
            ],
        },
        target,
    )
    assert with_date is not None
    assert with_date.posted_at is not None
    with_iso = to_posting(
        {
            "title": "B",
            "id": "y",
            "docattributes": [{"processedtime": "2026-01-02T03:04:05Z"}],
        },
        target,
    )
    assert with_iso is not None
    assert with_iso.posted_at is not None


def test_ibm_careers_api_path_without_app_id_segment() -> None:
    with pytest.raises(ValueError, match="app_id"):
        resolve_target(ScrapeContext(query_url="https://www-api.ibm.com/search/api/other"))


def test_ibm_careers_exits_while_when_limit_filled_on_full_page() -> None:
    payload = {
        "resultset": {
            "searchresults": {
                "totalresults": 100,
                "searchresultlist": [
                    {
                        "title": "One",
                        "docattributes": [{"field_text_01": "1"}],
                        "url": "https://careers.ibm.com/careers/JobDetail?jobId=1",
                    },
                    {
                        "title": "Two",
                        "docattributes": [{"field_text_01": "2"}],
                        "url": "https://careers.ibm.com/careers/JobDetail?jobId=2",
                    },
                ],
            }
        }
    }
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=payload)

    scraper = get_scraper("ibm_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(config={"max_results": 2, "page_size": 2, "company": "IBM"})
    )
    assert len(postings) == 2
    assert calls["n"] == 1


def test_ibm_careers_stops_when_offset_reaches_total() -> None:
    payload = {
        "resultset": {
            "searchresults": {
                "totalresults": 2,
                "searchresultlist": [
                    {
                        "title": "One",
                        "docattributes": [{"field_text_01": "1"}],
                        "url": "https://careers.ibm.com/careers/JobDetail?jobId=1",
                    },
                    {
                        "title": "Two",
                        "docattributes": [{"field_text_01": "2"}],
                        "url": "https://careers.ibm.com/careers/JobDetail?jobId=2",
                    },
                ],
            }
        }
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    scraper = get_scraper("ibm_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(config={"max_results": 50, "page_size": 2, "company": "IBM"})
    )
    assert len(postings) == 2


def test_ibm_careers_posted_at_invalid_date_only_falls_through() -> None:
    target = IbmCareersTarget(
        app_id="careers", scope="careers2", query="*", company="IBM"
    )
    posting = to_posting(
        {
            "title": "X",
            "id": "z",
            "docattributes": [{"dcdate": "not-a-date"}, {"field_text_01": "7"}],
        },
        target,
    )
    assert posting is not None
    assert posting.posted_at is None


def test_detect_ibm_careers_rejects_unrelated_hosts() -> None:
    from app.scrapers.url_detect_ibm import detect_ibm_careers
    from urllib.parse import urlparse

    parsed = urlparse("https://example.com/jobs")
    assert detect_ibm_careers(parsed, "example.com", None) is None


def test_detect_ibm_careers_api_wrong_path() -> None:
    assert detect_source_from_url("https://www-api.ibm.com/other") is None
    from app.scrapers.url_detect_ibm import detect_ibm_careers
    from urllib.parse import urlparse

    parsed = urlparse("https://www-api.ibm.com/search/api/v1-1/ibmcom/appid")
    assert detect_ibm_careers(parsed, "www-api.ibm.com", None) is None


def test_detect_ibm_careers_plain_careers_host() -> None:
    detected = detect_source_from_url("https://careers.ibm.com/")
    assert detected is not None
    assert "keywords" not in detected.default_config


def test_detect_ibm_careers_strips_page_title_suffix() -> None:
    detected = detect_source_from_url(
        "https://www.ibm.com/careers/search",
        page_title="Search jobs | IBM Careers",
    )
    assert detected is not None
    assert detected.suggested_name == "Search jobs"


def test_ibm_careers_preset_without_keywords() -> None:
    from app.portals.catalog_helpers_ibm import ibm_careers_preset

    bare = ibm_careers_preset(portal_id="ibm", company="IBM", keywords="")
    assert bare.base_url == "https://www.ibm.com/careers/search"
    assert "keywords" not in bare.default_config


def test_hashicorp_portal_preset_registered() -> None:
    preset = get_portal_preset("hashicorp")
    assert preset is not None
    assert preset.adapter_key == "ibm_careers"
    assert preset.default_config["keywords"] == "HashiCorp"
    assert preset.company_name == "HashiCorp"
    assert len(CURATED_PORTALS) == 121
    # Fixture still parses as JSON for CI smoke
    assert json.loads(load_fixture("ibm_careers_page1.json"))["resultset"]
