import json
from collections.abc import Callable
from unittest.mock import patch

import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from app.scrapers.adapters.workday import WorkdayScraper
from app.scrapers.base import Scraper
from tests.conftest import load_fixture, make_http_client

_CONFIG = {"tenant": "acme", "site": "AcmeCareers", "region": "wd5"}


def _make(handler: Callable[[httpx.Request], httpx.Response]) -> Scraper:
    return get_scraper("workday", http=make_http_client(handler))


def test_workday_rejects_non_dict_payload() -> None:
    scraper = _make(lambda r: httpx.Response(200, json=[1, 2]))
    with pytest.raises(ValueError, match="expected a JSON object"):
        scraper.fetch(ScrapeContext(config=_CONFIG))


def test_workday_rejects_bad_job_postings_field() -> None:
    scraper = _make(lambda r: httpx.Response(200, json={"jobPostings": "nope"}))
    with pytest.raises(ValueError, match="unexpected jobPostings field"):
        scraper.fetch(ScrapeContext(config=_CONFIG))


def test_workday_stops_on_empty_job_postings() -> None:
    scraper = _make(lambda r: httpx.Response(200, json={"total": 5, "jobPostings": []}))
    assert scraper.fetch(ScrapeContext(config=_CONFIG)) == []


def test_workday_search_text_from_filters_list() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"total": 0, "jobPostings": []})

    scraper = _make(handler)
    scraper.fetch(ScrapeContext(config=_CONFIG, filters={"keywords": ["python", "rust"]}))
    assert json.loads(seen["body"])["searchText"] == "python rust"


def test_workday_search_text_from_filters_string() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"total": 0, "jobPostings": []})

    scraper = _make(handler)
    scraper.fetch(ScrapeContext(config=_CONFIG, filters={"keywords_include": "golang"}))
    assert json.loads(seen["body"])["searchText"] == "golang"


def test_workday_rejects_bad_page_size() -> None:
    scraper = _make(lambda r: httpx.Response(200))
    with pytest.raises(ValueError, match="page_size must be a positive integer"):
        scraper.fetch(ScrapeContext(config={**_CONFIG, "page_size": True}))


def test_workday_rejects_non_positive_page_size() -> None:
    scraper = _make(lambda r: httpx.Response(200))
    with pytest.raises(ValueError, match="page_size must be a positive integer"):
        scraper.fetch(ScrapeContext(config={**_CONFIG, "page_size": 0}))


def test_workday_requires_tenant_and_site_without_query_url() -> None:
    scraper = _make(lambda r: httpx.Response(200))
    with pytest.raises(ValueError, match="needs a query_url or config.tenant"):
        scraper.fetch(ScrapeContext(config={"tenant": "acme"}))


def test_workday_board_url_without_locale_segment() -> None:
    fixture = load_fixture("workday_jobs.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = _make(handler)
    scraper.fetch(ScrapeContext(query_url="https://acme.wd5.myworkdayjobs.com/AcmeCareers"))
    assert seen["url"] == "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/AcmeCareers/jobs"


def test_workday_query_url_without_site_raises() -> None:
    scraper = _make(lambda r: httpx.Response(200))
    with pytest.raises(ValueError, match="could not determine site"):
        scraper.fetch(ScrapeContext(query_url="https://acme.wd5.myworkdayjobs.com/en-US/"))


def test_workday_plain_host_without_region() -> None:
    # A region-less *.myworkdayjobs.com host does not resolve in the sandbox,
    # so bypass the SSRF DNS check; we only assert on URL construction here.
    fixture = load_fixture("workday_jobs.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = _make(handler)
    with patch("app.scrapers.http.assert_safe_outbound_url"):
        scraper.fetch(ScrapeContext(query_url="https://acme.myworkdayjobs.com/en-US/AcmeCareers"))
    assert seen["url"] == "https://acme.myworkdayjobs.com/wday/cxs/acme/AcmeCareers/jobs"


def test_workday_rejects_non_workday_host() -> None:
    scraper = _make(lambda r: httpx.Response(200))
    with pytest.raises(ValueError, match="must be a \\*.myworkdayjobs.com URL"):
        scraper.fetch(ScrapeContext(query_url="https://acme.example.com/en-US/AcmeCareers"))


def test_workday_missing_tenant_from_query_url_raises() -> None:
    # _parse_host normally guarantees a tenant; patch it empty to exercise the
    # defensive "could not determine tenant" guard in the non-CXS branch.
    scraper = _make(lambda r: httpx.Response(200))
    with (
        patch.object(WorkdayScraper, "_parse_host", staticmethod(lambda host: ("", None))),
        pytest.raises(ValueError, match="could not determine tenant"),
    ):
        scraper.fetch(
            ScrapeContext(query_url="https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers")
        )


def test_workday_default_host_without_region_from_config() -> None:
    fixture = load_fixture("workday_jobs.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = _make(handler)
    with patch("app.scrapers.http.assert_safe_outbound_url"):
        scraper.fetch(ScrapeContext(config={"tenant": "acme", "site": "AcmeCareers"}))
    assert seen["url"] == "https://acme.myworkdayjobs.com/wday/cxs/acme/AcmeCareers/jobs"


def test_workday_posting_field_fallbacks() -> None:
    payload = {
        "total": 3,
        "jobPostings": [
            {"title": "No bullets, has path", "externalPath": "/job/x"},
            {"title": "Only title", "bulletFields": []},
            {"title": "Relative path", "externalPath": "relative/path", "bulletFields": ["JR9"]},
        ],
    }
    scraper = _make(lambda r: httpx.Response(200, json=payload))
    postings = scraper.fetch(ScrapeContext(config=_CONFIG))
    by_id = {p.external_id: p for p in postings}
    # No bulletFields -> external_id falls back to externalPath.
    assert "/job/x" in by_id
    assert by_id["/job/x"].url == ("https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers/job/x")
    # Empty bulletFields + empty externalPath -> falls back to title; board url.
    assert "Only title" in by_id
    assert by_id["Only title"].url == "https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers"
    # Relative externalPath (no leading slash) is appended with a slash.
    assert by_id["JR9"].url == (
        "https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers/relative/path"
    )
