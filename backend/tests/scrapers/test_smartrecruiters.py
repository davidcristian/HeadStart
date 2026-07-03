import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client


def test_smartrecruiters_tolerates_bad_date_and_nonfinite_total() -> None:
    """A malformed date and a JSON `Infinity` total must degrade, not crash the run."""
    payload = (
        '{"totalFound": Infinity, "content": [{"id": "1", "name": "Eng", "releasedDate": "x"}]}'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=payload, headers={"content-type": "application/json"})

    scraper = get_scraper("smartrecruiters", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"company_id": "AcmeCorp"}))

    assert len(postings) == 1
    assert postings[0].posted_at is None


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


def test_smartrecruiters_requires_company_id_without_query_url() -> None:
    scraper = get_scraper("smartrecruiters", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="needs a query_url or config.company_id"):
        scraper.fetch(ScrapeContext(config={"company": "ACME Corp"}))


def test_smartrecruiters_rejects_unrecognized_query_url() -> None:
    scraper = get_scraper("smartrecruiters", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="must be a careers board URL or Postings API URL"):
        scraper.fetch(
            ScrapeContext(
                query_url="https://example.com/jobs",
                config={"company": "ACME Corp"},
            )
        )


def test_smartrecruiters_rejects_malformed_api_url() -> None:
    scraper = get_scraper("smartrecruiters", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="could not determine company_id from API URL"):
        scraper.fetch(
            ScrapeContext(
                query_url="https://api.smartrecruiters.com/v1/companies",
                config={"company": "ACME Corp"},
            )
        )


def test_smartrecruiters_rejects_empty_board_url() -> None:
    scraper = get_scraper("smartrecruiters", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="could not determine company_id from board URL"):
        scraper.fetch(
            ScrapeContext(
                query_url="https://careers.smartrecruiters.com/",
                config={"company": "ACME Corp"},
            )
        )


def test_smartrecruiters_validates_page_size() -> None:
    scraper = get_scraper("smartrecruiters", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="page_size must be a positive integer"):
        scraper.fetch(
            ScrapeContext(config={"company_id": "AcmeCorp", "page_size": 0}),
        )
    with pytest.raises(ValueError, match="page_size must be a positive integer"):
        scraper.fetch(
            ScrapeContext(config={"company_id": "AcmeCorp", "page_size": "large"}),
        )


def test_smartrecruiters_rejects_unexpected_payload_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "an", "object"])

    scraper = get_scraper("smartrecruiters", http=make_http_client(handler))
    with pytest.raises(ValueError, match="unexpected payload"):
        scraper.fetch(ScrapeContext(config={"company_id": "AcmeCorp"}))


def test_smartrecruiters_rejects_unexpected_content_field() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"totalFound": 1, "content": "bad"})

    scraper = get_scraper("smartrecruiters", http=make_http_client(handler))
    with pytest.raises(ValueError, match="unexpected content field"):
        scraper.fetch(ScrapeContext(config={"company_id": "AcmeCorp"}))


def test_smartrecruiters_location_fallback_when_full_location_missing() -> None:
    payload = {
        "offset": 0,
        "limit": 1,
        "totalFound": 1,
        "content": [
            {
                "id": "1",
                "name": "Analyst",
                "company": {"identifier": "AcmeCorp", "name": "ACME Corp"},
                "location": {"city": "Austin", "region": "TX", "country": "us"},
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    scraper = get_scraper("smartrecruiters", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"company_id": "AcmeCorp"}))
    assert postings[0].location == "Austin, TX, us"


def test_smartrecruiters_empty_location_for_non_dict() -> None:
    payload = {
        "offset": 0,
        "limit": 1,
        "totalFound": 1,
        "content": [
            {
                "id": "2",
                "name": "Coordinator",
                "company": {"identifier": "AcmeCorp", "name": "ACME Corp"},
                "location": "Remote",
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    scraper = get_scraper("smartrecruiters", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"company_id": "AcmeCorp"}))
    assert postings[0].location == ""
