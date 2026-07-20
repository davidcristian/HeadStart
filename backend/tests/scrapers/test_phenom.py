"""Tests for the Phenom People scraper."""

from __future__ import annotations

import json

import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client

_SESSION_HTML = """
<html><script>
var phApp = {"refNum":"CISCISGLOBAL","csrfToken":"test-csrf"};
phApp.sessionParams = {"csrfToken":"test-csrf"};
</script></html>
"""


def _handler_with_pages(
    page1: str, page2: str | None = None, *, expect_keywords: str | None = None
):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        url = str(request.url)
        if request.method == "GET" and "search-results" in url:
            return httpx.Response(200, text=_SESSION_HTML)
        if request.method == "POST" and url.endswith("/widgets"):
            body = json.loads(request.content.decode())
            assert body["ddoKey"] == "refineSearch"
            assert request.headers.get("x-csrf-token") == "test-csrf"
            if expect_keywords is not None:
                assert body.get("keywords") == expect_keywords
            offset = int(body.get("from") or 0)
            if offset == 0:
                return httpx.Response(
                    200, text=page1, headers={"content-type": "application/json"}
                )
            if page2 is not None:
                return httpx.Response(
                    200, text=page2, headers={"content-type": "application/json"}
                )
            return httpx.Response(
                200,
                text='{"refineSearch":{"totalHits":0,"data":{"jobs":[]}}}',
                headers={"content-type": "application/json"},
            )
        raise AssertionError(f"unexpected request: {request.method} {url}")

    handler.seen = seen  # type: ignore[attr-defined]
    return handler


def test_phenom_parses_postings_with_pagination() -> None:
    page1 = load_fixture("phenom_jobs_page1.json")
    page2 = load_fixture("phenom_jobs_page2.json")
    handler = _handler_with_pages(page1, page2)
    scraper = get_scraper("phenom", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://careers.cisco.com/global/en/search-results",
            config={"company": "Splunk", "page_size": 2, "ref_num": "CISCISGLOBAL"},
        )
    )

    assert len(postings) == 3
    first = postings[0]
    assert first.external_id == "CISCISGLOBAL2015573EXTERNALENGLOBAL"
    assert first.title == "Customer Success Splunk Platform Area TAM"
    assert first.company == "Splunk"
    assert first.location == "Richardson, Texas, United States of America"
    assert (
        first.url
        == "https://careers.cisco.com/global/en/job/CISCISGLOBAL2015573EXTERNALENGLOBAL"
    )
    assert first.posted_at is not None
    assert postings[2].title == "Account Executive - Splunk"
    assert first.content_hash() != postings[2].content_hash()


def test_phenom_uses_careers_base_url_and_discovers_ref_num() -> None:
    page1 = load_fixture("phenom_jobs_page1.json")
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        payloads.append(json.loads(request.content.decode()))
        return httpx.Response(200, text=page1, headers={"content-type": "application/json"})

    scraper = get_scraper("phenom", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            config={
                "careers_base_url": "https://careers.cisco.com",
                "country": "global",
                "locale": "en_global",
                "page_size": 50,
            }
        )
    )

    assert payloads[0]["refNum"] == "CISCISGLOBAL"
    assert payloads[0]["country"] == "global"
    assert payloads[0]["lang"] == "en_global"


def test_phenom_sends_keywords_from_config_and_filters() -> None:
    page1 = load_fixture("phenom_jobs_page1.json")
    handler = _handler_with_pages(page1, expect_keywords="Splunk")
    scraper = get_scraper("phenom", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://careers.cisco.com/",
            config={"company": "Splunk", "keywords": "Splunk", "page_size": 2},
        )
    )

    handler = _handler_with_pages(page1, expect_keywords="engineer")
    scraper = get_scraper("phenom", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://careers.cisco.com/",
            filters={"keywords": "engineer"},
            config={"page_size": 2},
        )
    )


def test_phenom_sends_selected_fields() -> None:
    page1 = load_fixture("phenom_jobs_page1.json")
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        payloads.append(json.loads(request.content.decode()))
        return httpx.Response(200, text=page1)

    scraper = get_scraper("phenom", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://careers.cisco.com/",
            config={
                "selected_fields": {"company": ["743 Splunk Services"]},
                "page_size": 2,
            },
        )
    )
    assert payloads[0]["selected_fields"] == {"company": ["743 Splunk Services"]}


def test_phenom_rejects_missing_base() -> None:
    scraper = get_scraper("phenom", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="query_url or config.careers_base_url"):
        scraper.fetch(ScrapeContext())


def test_phenom_rejects_non_http_query_url() -> None:
    scraper = get_scraper("phenom", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="http\\(s\\)"):
        scraper.fetch(ScrapeContext(query_url="ftp://careers.cisco.com/jobs"))


def test_phenom_rejects_non_dict_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        return httpx.Response(200, text="[]", headers={"content-type": "application/json"})

    scraper = get_scraper("phenom", http=make_http_client(handler))
    with pytest.raises(ValueError, match="JSON object"):
        scraper.fetch(ScrapeContext(query_url="https://careers.cisco.com/"))


def test_phenom_rejects_bad_refine_search() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        return httpx.Response(
            200, text='{"refineSearch": []}', headers={"content-type": "application/json"}
        )

    scraper = get_scraper("phenom", http=make_http_client(handler))
    with pytest.raises(ValueError, match="refineSearch"):
        scraper.fetch(ScrapeContext(query_url="https://careers.cisco.com/"))


def test_phenom_rejects_non_list_jobs() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        return httpx.Response(
            200,
            text='{"refineSearch":{"data":{"jobs":{}}}}',
            headers={"content-type": "application/json"},
        )

    scraper = get_scraper("phenom", http=make_http_client(handler))
    with pytest.raises(ValueError, match="jobs field"):
        scraper.fetch(ScrapeContext(query_url="https://careers.cisco.com/"))


def test_phenom_stops_on_empty_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        return httpx.Response(
            200,
            text='{"refineSearch":{"totalHits":0,"data":{"jobs":[]}}}',
            headers={"content-type": "application/json"},
        )

    scraper = get_scraper("phenom", http=make_http_client(handler))
    assert scraper.fetch(ScrapeContext(query_url="https://careers.cisco.com/")) == []


def test_phenom_skips_invalid_and_duplicate_rows() -> None:
    payload = {
        "refineSearch": {
            "totalHits": 4,
            "data": {
                "jobs": [
                    {
                        "jobSeqNo": "A1",
                        "title": "Engineer",
                        "location": "Remote",
                    },
                    "nope",
                    {"jobSeqNo": "", "title": "Missing id"},
                    {"jobSeqNo": "A1", "title": "Dup"},
                ]
            },
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        return httpx.Response(
            200, text=json.dumps(payload), headers={"content-type": "application/json"}
        )

    scraper = get_scraper("phenom", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(query_url="https://careers.cisco.com/"))
    assert len(postings) == 1
    assert postings[0].external_id == "A1"


def test_phenom_stops_when_max_results_reached() -> None:
    page1 = load_fixture("phenom_jobs_page1.json")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        calls["n"] += 1
        return httpx.Response(200, text=page1)

    scraper = get_scraper("phenom", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://careers.cisco.com/",
            config={"page_size": 2, "max_results": 1},
        )
    )
    assert len(postings) == 1
    assert calls["n"] == 1


def test_phenom_rejects_bad_page_size_and_selected_fields() -> None:
    scraper = get_scraper("phenom", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="page_size"):
        scraper.fetch(
            ScrapeContext(
                query_url="https://careers.cisco.com/",
                config={"page_size": 0},
            )
        )
    with pytest.raises(ValueError, match="page_size"):
        scraper.fetch(
            ScrapeContext(
                query_url="https://careers.cisco.com/",
                config={"page_size": "big"},
            )
        )
    with pytest.raises(ValueError, match="max_results"):
        scraper.fetch(
            ScrapeContext(
                query_url="https://careers.cisco.com/",
                config={"max_results": 0},
            )
        )
    with pytest.raises(ValueError, match="max_results"):
        scraper.fetch(
            ScrapeContext(
                query_url="https://careers.cisco.com/",
                config={"max_results": True},
            )
        )
    with pytest.raises(ValueError, match="selected_fields"):
        scraper.fetch(
            ScrapeContext(
                query_url="https://careers.cisco.com/",
                config={"selected_fields": ["nope"]},
            )
        )
    with pytest.raises(ValueError, match="selected_fields values"):
        scraper.fetch(
            ScrapeContext(
                query_url="https://careers.cisco.com/",
                config={"selected_fields": {"company": "x"}},
            )
        )


def test_phenom_locale_from_path_variants_and_selected_fields_cleanup() -> None:
    page1 = load_fixture("phenom_jobs_page1.json")
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert "/us/en/search-results" in str(request.url) or "/ca/fr/search-results" in str(
                request.url
            )
            return httpx.Response(200, text=_SESSION_HTML)
        payloads.append(json.loads(request.content.decode()))
        return httpx.Response(200, text=page1)

    scraper = get_scraper("phenom", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://careers.cisco.com/us/en_us/search-results",
            config={
                "page_size": 2,
                "selected_fields": {"": ["x"], "company": ["", "  ", "Acme"]},
            },
        )
    )
    assert payloads[0]["lang"] == "en_us"
    assert payloads[0]["country"] == "us"
    assert payloads[0]["selected_fields"] == {"company": ["Acme"]}

    payloads.clear()
    scraper.fetch(
        ScrapeContext(
            query_url="https://careers.cisco.com/ca/fr/search-results",
            config={"page_size": 2},
        )
    )
    assert payloads[0]["lang"] == "fr_ca"
    assert payloads[0]["country"] == "ca"


def test_phenom_location_falls_back_to_parts() -> None:
    payload = {
        "refineSearch": {
            "totalHits": 1,
            "jobs": [
                {
                    "jobId": "99",
                    "title": "Analyst",
                    "city": "Austin",
                    "state": "Texas",
                    "country": "USA",
                }
            ],
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text="<html></html>")
        return httpx.Response(200, text=json.dumps(payload))

    scraper = get_scraper("phenom", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(query_url="https://careers.cisco.com/", config={"company": "Acme"})
    )
    assert postings[0].location == "Austin, Texas, USA"
    assert postings[0].url.endswith("/us/en/job/99")


def test_phenom_total_hits_from_inner_and_company_fallback() -> None:
    payload = {
        "refineSearch": {
            "data": {
                "totalHits": 1,
                "jobs": [
                    {
                        "reqId": "42",
                        "title": "Ops",
                        "company": "FromJob",
                        "cityState": "Seattle, WA",
                        "postedDate": None,
                    }
                ],
            }
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text="<html></html>")
        return httpx.Response(200, text=json.dumps(payload))

    scraper = get_scraper("phenom", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(query_url="https://careers.cisco.com/"))
    assert len(postings) == 1
    assert postings[0].company == "FromJob"
    assert postings[0].location == "Seattle, WA"
    assert postings[0].external_id == "42"
    assert postings[0].posted_at is None


def test_phenom_stops_when_offset_reaches_total_hits() -> None:
    page = {
        "refineSearch": {
            "totalHits": 2,
            "data": {
                "jobs": [
                    {"jobSeqNo": "1", "title": "A", "location": "X"},
                    {"jobSeqNo": "2", "title": "B", "location": "Y"},
                ]
            },
        }
    }
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        calls["n"] += 1
        return httpx.Response(200, text=json.dumps(page))

    scraper = get_scraper("phenom", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://careers.cisco.com/",
            config={"page_size": 2},
        )
    )
    assert len(postings) == 2
    assert calls["n"] == 1


def test_phenom_selected_fields_skips_empty_value_lists() -> None:
    page1 = load_fixture("phenom_jobs_page1.json")
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        payloads.append(json.loads(request.content.decode()))
        return httpx.Response(200, text=page1)

    scraper = get_scraper("phenom", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://careers.cisco.com/",
            config={
                "page_size": 2,
                "selected_fields": {"company": ["", "   "], "city": ["Austin"]},
            },
        )
    )
    assert payloads[0]["selected_fields"] == {"city": ["Austin"]}


def test_phenom_stops_when_page_adds_no_new_jobs() -> None:
    payload = {
        "refineSearch": {
            "data": {
                "jobs": [
                    {"jobSeqNo": "1", "title": "A", "location": "X"},
                    {"jobSeqNo": "2", "title": "B", "location": "Y"},
                ]
            }
        }
    }
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=_SESSION_HTML)
        calls["n"] += 1
        return httpx.Response(200, text=json.dumps(payload))

    scraper = get_scraper("phenom", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://careers.cisco.com/",
            config={"page_size": 2},
        )
    )
    assert len(postings) == 2
    assert calls["n"] == 2
