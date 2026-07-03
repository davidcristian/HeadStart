import httpx

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client


def test_smartrecruiters_parses_postings_with_pagination() -> None:
    page1 = load_fixture("smartrecruiters_postings_page1.json")
    page2 = load_fixture("smartrecruiters_postings_page2.json")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        assert "api.smartrecruiters.com" in str(request.url)
        if "offset=0" in str(request.url):
            return httpx.Response(200, text=page1, headers={"content-type": "application/json"})
        if "offset=2" in str(request.url):
            return httpx.Response(200, text=page2, headers={"content-type": "application/json"})
        raise AssertionError(f"unexpected request: {request.url}")

    scraper = get_scraper("smartrecruiters", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(config={"company_id": "AcmeCorp", "company": "ACME Corp"})
    )

    assert len(postings) == 3
    assert len(seen) == 2
    first = postings[0]
    assert first.external_id == "744000120624847"
    assert first.title == "Senior Software Engineer"
    assert first.company == "ACME Corp"
    assert first.location == "London, England, United Kingdom"
    assert first.url == "https://jobs.smartrecruiters.com/AcmeCorp/744000120624847"
    assert first.posted_at is not None
    assert postings[1].location == "Berlin, Berlin, de"
    assert postings[2].title == "Product Manager"
    assert first.content_hash() != postings[1].content_hash()


def test_smartrecruiters_uses_explicit_api_query_url() -> None:
    fixture = load_fixture("smartrecruiters_postings_page1.json")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("smartrecruiters", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://api.smartrecruiters.com/v1/companies/AcmeCorp/postings",
            config={"company": "ACME Corp"},
        )
    )

    assert seen[0].startswith("https://api.smartrecruiters.com/v1/companies/AcmeCorp/postings?")
    assert "limit=100" in seen[0]
    assert "offset=0" in seen[0]


def test_smartrecruiters_accepts_careers_board_url() -> None:
    fixture = load_fixture("smartrecruiters_postings_page1.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("smartrecruiters", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://careers.smartrecruiters.com/AcmeCorp",
            config={"company": "ACME Corp"},
        )
    )

    assert "companies/AcmeCorp/postings" in seen["url"]


def test_smartrecruiters_accepts_jobs_board_url() -> None:
    fixture = load_fixture("smartrecruiters_postings_page1.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("smartrecruiters", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://jobs.smartrecruiters.com/AcmeCorp",
            config={"company": "ACME Corp"},
        )
    )

    assert "companies/AcmeCorp/postings" in seen["url"]
