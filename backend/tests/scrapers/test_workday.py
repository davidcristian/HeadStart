import json

import httpx

from app.scrapers import ScrapeContext, get_scraper
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
