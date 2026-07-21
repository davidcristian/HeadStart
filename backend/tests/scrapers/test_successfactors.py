"""Tests for the SuccessFactors Career Site Builder scraper."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from app.portals import CURATED_PORTALS
from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client

_SESSION_HTML = """
<html><script type="text/javascript">
//<![CDATA[
$.ajaxSetup({
  cache: false,
  headers: {
    "X-CSRF-Token": "test-csrf-token"
  }
});
//]]>
</script>
<a href="/go/All-Jobs/9813400/">All Jobs</a>
<a href="/go/Engineering/9812500/">Engineering</a>
</html>
"""


def _handler_with_pages(
    page1: str,
    page2: str | None = None,
    *,
    expect_keywords: str | None = None,
    expect_category_id: int = 9813400,
):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        url = str(request.url)
        if request.method == "GET" and url.rstrip("/").endswith("wlgore.jobs.hr.cloud.sap"):
            return httpx.Response(200, text=_SESSION_HTML)
        if request.method == "POST" and url.endswith("/services/recruiting/v1/jobs"):
            body = json.loads(request.content.decode())
            assert request.headers.get("x-csrf-token") == "test-csrf-token"
            assert body["categoryId"] == expect_category_id
            if expect_keywords is not None:
                assert body.get("keywords") == expect_keywords
            page = int(body.get("pageNumber") or 0)
            if page == 0:
                return httpx.Response(200, text=page1, headers={"content-type": "application/json"})
            if page2 is not None:
                return httpx.Response(200, text=page2, headers={"content-type": "application/json"})
            return httpx.Response(
                200,
                text='{"jobSearchResult":[],"totalJobs":0}',
                headers={"content-type": "application/json"},
            )
        raise AssertionError(f"unexpected request: {request.method} {url}")

    handler.seen = seen  # type: ignore[attr-defined]
    return handler


def test_successfactors_parses_postings_with_pagination() -> None:
    page1 = load_fixture("successfactors_jobs_page1.json")
    page2 = load_fixture("successfactors_jobs_page2.json")
    handler = _handler_with_pages(page1, page2)
    scraper = get_scraper("successfactors", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://wlgore.jobs.hr.cloud.sap/",
            config={"company": "W. L. Gore & Associates"},
        )
    )

    assert len(postings) == 12
    first = postings[0]
    assert first.external_id == "1746"
    assert first.title.startswith("Internship (f/m/d) Footwear")
    assert first.company == "W. L. Gore & Associates"
    assert first.location == "Feldkirchen/Westerham, BY, DEU, D-83620"
    assert first.url == (
        "https://wlgore.jobs.hr.cloud.sap/job/"
        "Internship-%28fmd%29-Footwear-Gloves-&-Accessories-Strategic-Marketing-"
        "and-Product-Management-Support/1746-en_US/"
    )
    assert first.posted_at == datetime(2026, 6, 3, tzinfo=UTC)
    assert postings[10].title == "Pricing Analyst"
    assert postings[11].location == "Elkton, MD, USA, 21921"
    assert first.content_hash() != postings[10].content_hash()


def test_successfactors_uses_careers_base_url_and_configured_category() -> None:
    page1 = load_fixture("successfactors_jobs_page1.json")
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        payloads.append(json.loads(request.content.decode()))
        return httpx.Response(200, text=page1)

    scraper = get_scraper("successfactors", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            config={
                "careers_base_url": "https://wlgore.jobs.hr.cloud.sap",
                "category_id": 9812500,
                "locale": "en_US",
            }
        )
    )

    assert payloads[0]["categoryId"] == 9812500
    assert postings[0].company == "Wlgore"
    assert postings[0].url.endswith("/1746-en_US/")


def test_successfactors_filters_keywords_client_side() -> None:
    page1 = load_fixture("successfactors_jobs_page1.json")
    page2 = load_fixture("successfactors_jobs_page2.json")
    handler = _handler_with_pages(page1, page2, expect_keywords="Pricing")
    scraper = get_scraper("successfactors", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://wlgore.jobs.hr.cloud.sap/",
            config={"company": "Gore", "keywords": "Pricing"},
        )
    )
    assert len(postings) == 1
    assert postings[0].title == "Pricing Analyst"


def test_successfactors_keywords_from_filters() -> None:
    page1 = load_fixture("successfactors_jobs_page1.json")
    handler = _handler_with_pages(page1, expect_keywords="GORE-TEX")
    scraper = get_scraper("successfactors", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://wlgore.jobs.hr.cloud.sap/",
            filters={"keywords": "GORE-TEX"},
            config={"company": "Gore"},
        )
    )
    assert len(postings) == 1
    assert "GORE-TEX" in postings[0].title


def test_successfactors_accepts_jobs_api_query_url() -> None:
    page1 = load_fixture("successfactors_jobs_page1.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen[request.method] = str(request.url)
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        return httpx.Response(200, text=page1)

    scraper = get_scraper("successfactors", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://wlgore.jobs.hr.cloud.sap/services/recruiting/v1/jobs",
            config={"company": "Gore"},
        )
    )
    assert seen["GET"].rstrip("/").endswith("wlgore.jobs.hr.cloud.sap")
    assert seen["POST"].endswith("/services/recruiting/v1/jobs")


def test_successfactors_max_results_caps_output() -> None:
    page1 = load_fixture("successfactors_jobs_page1.json")
    handler = _handler_with_pages(page1)
    scraper = get_scraper("successfactors", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://wlgore.jobs.hr.cloud.sap/",
            config={"company": "Gore", "max_results": 2},
        )
    )
    assert len(postings) == 2


def test_successfactors_rejects_missing_base() -> None:
    scraper = get_scraper("successfactors", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="careers_base_url"):
        scraper.fetch(ScrapeContext())


def test_successfactors_rejects_bad_host_query_url() -> None:
    scraper = get_scraper("successfactors", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="jobs.hr.cloud.sap"):
        scraper.fetch(ScrapeContext(query_url="https://example.com/careers"))


def test_successfactors_rejects_missing_csrf() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text="<html><a href='/go/All-Jobs/1/'>All</a></html>")
        raise AssertionError("should not POST without CSRF")

    scraper = get_scraper("successfactors", http=make_http_client(handler))
    with pytest.raises(ValueError, match="X-CSRF-Token"):
        scraper.fetch(ScrapeContext(query_url="https://wlgore.jobs.hr.cloud.sap/"))


def test_successfactors_rejects_missing_category() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                text='<html><script>headers:{"X-CSRF-Token":"tok"}</script></html>',
            )
        raise AssertionError("should not POST without category")

    scraper = get_scraper("successfactors", http=make_http_client(handler))
    with pytest.raises(ValueError, match="categoryId"):
        scraper.fetch(ScrapeContext(query_url="https://wlgore.jobs.hr.cloud.sap/"))


def test_successfactors_rejects_non_object_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        return httpx.Response(200, text="[]", headers={"content-type": "application/json"})

    scraper = get_scraper("successfactors", http=make_http_client(handler))
    with pytest.raises(ValueError, match="JSON object"):
        scraper.fetch(ScrapeContext(query_url="https://wlgore.jobs.hr.cloud.sap/"))


def test_successfactors_rejects_bad_job_search_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        return httpx.Response(
            200,
            text='{"jobSearchResult":{}}',
            headers={"content-type": "application/json"},
        )

    scraper = get_scraper("successfactors", http=make_http_client(handler))
    with pytest.raises(ValueError, match="jobSearchResult"):
        scraper.fetch(ScrapeContext(query_url="https://wlgore.jobs.hr.cloud.sap/"))


def test_successfactors_skips_invalid_rows_and_empty_pages() -> None:
    payload = {
        "jobSearchResult": [
            "nope",
            {"response": {"id": "", "unifiedStandardTitle": "Missing id"}},
            {"response": {"id": "1", "unifiedStandardTitle": ""}},
            {
                "response": {
                    "id": "9",
                    "unifiedStandardTitle": "Valid Role",
                    "urlTitle": "Valid-Role",
                    "jobLocationShort": ["Remote<br/>"],
                }
            },
        ],
        "totalJobs": 1,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        body = json.loads(request.content.decode())
        if body["pageNumber"] == 0:
            return httpx.Response(200, json=payload)
        return httpx.Response(200, json={"jobSearchResult": [], "totalJobs": 1})

    scraper = get_scraper("successfactors", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(query_url="https://wlgore.jobs.hr.cloud.sap/", config={"company": "Gore"})
    )
    assert len(postings) == 1
    assert postings[0].external_id == "9"
    assert postings[0].location == "Remote"


@pytest.mark.parametrize(
    ("raw", "match"),
    [
        ({"max_results": 0}, "max_results"),
        ({"max_results": "nope"}, "max_results"),
        ({"category_id": 0}, "category_id"),
        ({"category_id": "nope"}, "category_id"),
        ({"category_id": True}, "category_id"),
    ],
)
def test_successfactors_config_validation(raw: dict, match: str) -> None:
    scraper = get_scraper("successfactors", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match=match):
        scraper.fetch(
            ScrapeContext(
                query_url="https://wlgore.jobs.hr.cloud.sap/",
                config={"company": "Gore", **raw},
            )
        )


def test_successfactors_empty_csrf_rejected() -> None:
    html = '<script>headers:{"X-CSRF-Token":"   "}</script><a href="/go/All-Jobs/1/">x</a>'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    scraper = get_scraper("successfactors", http=make_http_client(handler))
    with pytest.raises(ValueError, match="empty X-CSRF-Token"):
        scraper.fetch(ScrapeContext(query_url="https://wlgore.jobs.hr.cloud.sap/"))


def test_successfactors_prefers_first_category_when_no_all_jobs() -> None:
    html = """
    <script>headers:{"X-CSRF-Token":"tok"}</script>
    <a href="/go/Engineering/42/">Engineering</a>
    """
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=html)
        payloads.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={"jobSearchResult": [], "totalJobs": 0})

    scraper = get_scraper("successfactors", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(query_url="https://wlgore.jobs.hr.cloud.sap/"))
    assert payloads[0]["categoryId"] == 42


def test_successfactors_preset_optional_category_id() -> None:
    from app.portals.catalog_helpers_successfactors import successfactors_preset

    preset = successfactors_preset(
        portal_id="acme-sf",
        company="Acme",
        careers_base_url="https://acme.jobs.hr.cloud.sap/",
        category_id=123,
    )
    assert preset.default_config["category_id"] == 123
    assert preset.base_url == "https://acme.jobs.hr.cloud.sap"
    assert len(CURATED_PORTALS) == 167
    preset = next(p for p in CURATED_PORTALS if p.id == "wlgore")
    assert preset.adapter_key == "successfactors"
    assert preset.default_config["careers_base_url"] == "https://wlgore.jobs.hr.cloud.sap"


def test_successfactors_parse_helpers_cover_edge_cases() -> None:
    from app.scrapers.adapters.successfactors_parse import (
        SuccessFactorsTarget,
        _company_from_host,
        _location,
        _posted_at,
        extract_page,
        resolve_target,
        to_posting,
    )

    with pytest.raises(ValueError, match="http\\(s\\) origin"):
        resolve_target(ScrapeContext(config={"careers_base_url": "ftp://wlgore.jobs.hr.cloud.sap"}))

    with pytest.raises(ValueError, match="http\\(s\\) careers"):
        resolve_target(ScrapeContext(query_url="not-a-url"))

    target = resolve_target(
        ScrapeContext(query_url="https://jobs.hr.cloud.sap/services/recruiting/v1/jobs")
    )
    assert target.careers_base_url == "https://jobs.hr.cloud.sap"

    vanity = resolve_target(
        ScrapeContext(query_url="https://careers.example.com/services/recruiting/v1/jobs")
    )
    assert vanity.careers_base_url == "https://careers.example.com"

    nested = resolve_target(
        ScrapeContext(query_url="https://us.acme.jobs.hr.cloud.sap/", config={})
    )
    assert nested.company == "Us"

    jobs, total = extract_page({})
    assert jobs == [] and total is None
    jobs, total = extract_page({"jobSearchResult": [{"response": "nope"}], "totalJobs": True})
    assert jobs == [] and total is None
    jobs, total = extract_page({"jobSearchResult": [], "totalJobs": -1})
    assert total is None

    posting = to_posting(
        {
            "id": "42",
            "title": "Fallback Title",
            "jobLocationCountry": ["Germany"],
            "postedDate": "2026-07-01T12:00:00Z",
        },
        SuccessFactorsTarget(
            careers_base_url="https://wlgore.jobs.hr.cloud.sap",
            company="Gore",
            locale="en_US",
            keywords="",
            category_id=None,
        ),
    )
    assert posting is not None
    assert posting.url == "https://wlgore.jobs.hr.cloud.sap/job/42"
    assert posting.location == "Germany"
    assert posting.posted_at == datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

    assert _location({"jobLocationShort": [1, None], "jobLocationCountry": [""]}) == ""
    assert _location({"jobLocationShort": ["  "], "jobLocationCountry": ["USA"]}) == "USA"
    assert _location({"jobLocationShort": [], "jobLocationCountry": []}) == ""
    assert _posted_at({"unifiedStandardStart": "07/04/2026"}) == datetime(2026, 7, 4, tzinfo=UTC)
    assert _posted_at({"startDate": "not-a-date", "postedDate": "also-bad"}) is None
    assert _company_from_host("example.com") == "example.com"
    assert _company_from_host(".jobs.hr.cloud.sap") == ".jobs.hr.cloud.sap"
