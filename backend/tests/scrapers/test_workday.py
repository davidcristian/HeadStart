import json
from collections.abc import Callable
from unittest.mock import patch

import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from app.scrapers.base import Scraper
from tests.conftest import load_fixture, make_http_client


def test_workday_parses_postings() -> None:
    fixture = load_fixture("workday_jobs.json")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/wday/cxs/acme/AcmeCareers/jobs")
        seen["body"] = request.read().decode()
        seen["referer"] = request.headers.get("referer")
        return httpx.Response(200, text=fixture, headers={"content-type": "application/json"})

    scraper = get_scraper("workday", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            config={
                "tenant": "acme",
                "site": "AcmeCareers",
                "region": "wd5",
                "company": "ACME",
            }
        )
    )

    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "JR1001"
    assert first.title == "Senior Software Engineer"
    assert first.company == "ACME"
    assert first.location == "Santa Clara, CA"
    assert (
        first.url
        == "https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"
    )
    assert first.content_hash() != postings[1].content_hash()
    body = json.loads(seen["body"])
    assert body["searchText"] == ""
    assert seen["referer"] == "https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers"


def test_workday_accepts_careers_page_url() -> None:
    fixture = load_fixture("workday_jobs.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("workday", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers",
            config={"company": "ACME"},
        )
    )

    assert seen["url"] == "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/AcmeCareers/jobs"


def test_workday_accepts_cxs_api_url() -> None:
    fixture = load_fixture("workday_jobs.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("workday", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/AcmeCareers/jobs",
            config={"company": "ACME"},
        )
    )

    assert seen["url"] == "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/AcmeCareers/jobs"


def test_workday_search_text_from_config() -> None:
    fixture = load_fixture("workday_jobs.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode()
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("workday", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            config={
                "tenant": "acme",
                "site": "AcmeCareers",
                "region": "wd5",
                "search_text": "platform engineer",
            }
        )
    )

    body = json.loads(seen["body"])
    assert body["searchText"] == "platform engineer"


def test_workday_paginates() -> None:
    page1 = (
        '{"total": 3, "jobPostings": [{"title": "Job A", "externalPath": "/job/a", '
        '"locationsText": "Remote", "bulletFields": ["A1"]}]}'
    )
    page2 = (
        '{"total": 3, "jobPostings": [{"title": "Job B", "externalPath": "/job/b", '
        '"locationsText": "Remote", "bulletFields": ["B1"]}, {"title": "Job C", '
        '"externalPath": "/job/c", "locationsText": "Remote", "bulletFields": ["C1"]}]}'
    )
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        calls.append(body)
        payload = json.loads(body)
        if payload["offset"] == 0:
            return httpx.Response(200, text=page1)
        return httpx.Response(200, text=page2)

    scraper = get_scraper("workday", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            config={
                "tenant": "acme",
                "site": "AcmeCareers",
                "region": "wd5",
                "page_size": 1,
            }
        )
    )

    assert len(postings) == 3
    assert len(calls) == 2
    assert json.loads(calls[0])["offset"] == 0
    assert json.loads(calls[1])["offset"] == 1


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


@pytest.mark.parametrize("total", ["Infinity", "NaN", "-Infinity"])
def test_workday_nonfinite_total_fallback(total: str) -> None:
    """JSON Infinity/NaN total must not raise on int()."""
    body = (
        '{"total": ' + total + ', "jobPostings": [{"title": "Eng", "externalPath": "/job/a", '
        '"bulletFields": ["REQ-1"]}]}'
    )
    scraper = _make(
        lambda r: httpx.Response(200, text=body, headers={"content-type": "application/json"})
    )
    postings = scraper.fetch(ScrapeContext(config=_CONFIG))
    assert len(postings) == 1
    assert postings[0].title == "Eng"


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
    with pytest.raises(ValueError, match="myworkdayjobs\\.com or \\*\\.myworkdaysite\\.com"):
        scraper.fetch(ScrapeContext(query_url="https://acme.example.com/en-US/AcmeCareers"))


def test_workday_missing_tenant_from_query_url_raises() -> None:
    # parse_host normally guarantees a tenant on jobs hosts; empty tenant exercises
    # the defensive guard in board_from_url's non-CXS branch.
    from app.scrapers.adapters import workday_parse

    scraper = _make(lambda r: httpx.Response(200))
    with (
        patch.object(workday_parse, "parse_host", lambda host: ("", "wd5", "jobs")),
        pytest.raises(ValueError, match="could not determine tenant"),
    ):
        scraper.fetch(
            ScrapeContext(query_url="https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers")
        )


def test_workday_accepts_myworkdaysite_recruiting_url() -> None:
    fixture = load_fixture("workday_jobs.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["referer"] = request.headers.get("referer")
        return httpx.Response(200, text=fixture)

    scraper = _make(handler)
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://wd1.myworkdaysite.com/recruiting/snapchat/snap",
            config={"company": "Snap"},
        )
    )
    assert seen["url"] == "https://wd1.myworkdaysite.com/wday/cxs/snapchat/snap/jobs"
    assert seen["referer"] == "https://wd1.myworkdaysite.com/recruiting/snapchat/snap"
    assert postings[0].company == "Snap"
    assert postings[0].url.startswith("https://wd1.myworkdaysite.com/recruiting/snapchat/snap/job/")


def test_workday_site_host_kind_from_config() -> None:
    fixture = load_fixture("workday_jobs.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = _make(handler)
    scraper.fetch(
        ScrapeContext(
            config={
                "tenant": "snapchat",
                "site": "snap",
                "region": "wd1",
                "host_kind": "site",
                "company": "Snap",
            }
        )
    )
    assert seen["url"] == "https://wd1.myworkdaysite.com/wday/cxs/snapchat/snap/jobs"


def test_workday_site_host_kind_requires_region() -> None:
    scraper = _make(lambda r: httpx.Response(200))
    with pytest.raises(ValueError, match="require config.region"):
        scraper.fetch(
            ScrapeContext(config={"tenant": "snapchat", "site": "snap", "host_kind": "site"})
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
