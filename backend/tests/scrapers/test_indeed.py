"""Tests for the Indeed job-search scraper."""

import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from app.scrapers.adapters.indeed import IndeedScraper
from tests.conftest import load_fixture, make_http_client

SEARCH_URL = "https://www.indeed.com/jobs?q=python&l=remote"


def _mosaic_html(results: str, tiers: str = '[{"jobCount":2}]') -> str:
    return (
        "<html><body><script>"
        'window.mosaic.providerData["mosaic-provider-jobcards"]='
        '{"metaData":{"mosaicProviderJobCardsModel":'
        f'{{"results":[{results}],"tierSummaries":{tiers}}}}}}};'
        "</script></body></html>"
    )


def _job_json(jobkey: str, title: str = "Role") -> str:
    return (
        f'{{"jobkey":"{jobkey}","title":"{title}",'
        f'"company":"Acme","formattedLocation":"Remote",'
        f'"viewJobLink":"/viewjob?jk={jobkey}"}}'
    )


def test_indeed_parses_mosaic_json() -> None:
    fixture = load_fixture("indeed_search.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("indeed", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(query_url=SEARCH_URL))

    assert seen["url"] == SEARCH_URL
    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "abc123def4567890"
    assert first.title == "Senior Python Developer"
    assert first.company == "Acme Corp"
    assert first.location == "Remote"
    assert first.url == "https://www.indeed.com/viewjob?jk=abc123def4567890"
    assert first.posted_at is not None
    assert postings[1].title == "Backend Engineer"


def test_indeed_builds_search_url_from_config() -> None:
    fixture = load_fixture("indeed_search.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("indeed", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(config={"q": "python", "l": "remote"}))

    assert seen["url"] == "https://www.indeed.com/jobs?q=python&l=remote&filter=0"


def test_indeed_paginates_with_start_offset() -> None:
    page_one = load_fixture("indeed_search_paged.html")
    page_two = load_fixture("indeed_search_page2.html")
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        if "start=10" in str(request.url):
            return httpx.Response(200, text=page_two)
        return httpx.Response(200, text=page_one)

    scraper = get_scraper("indeed", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(query_url=SEARCH_URL, config={"max_results": 3, "page_size": 10})
    )

    assert len(urls) == 2
    assert "start=10" in urls[1]
    assert len(postings) == 3
    assert postings[-1].title == "DevOps Engineer"


def test_indeed_falls_back_to_html_cards() -> None:
    fixture = load_fixture("indeed_search_cards.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("indeed", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(query_url=SEARCH_URL))

    assert len(postings) == 1
    assert postings[0].external_id == "htmljob00000001"
    assert postings[0].title == "Data Engineer"
    assert postings[0].company == "Gamma LLC"
    assert postings[0].location == "New York, NY"


def test_indeed_rejects_captcha_page() -> None:
    captcha_html = "<html><title>Security Check - Indeed.com</title></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=captcha_html)

    scraper = get_scraper("indeed", http=make_http_client(handler))
    try:
        scraper.fetch(ScrapeContext(query_url=SEARCH_URL))
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "Cloudflare" in str(exc)


def test_indeed_stops_when_page_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body></body></html>")

    scraper = get_scraper("indeed", http=make_http_client(handler))
    assert scraper.fetch(ScrapeContext(query_url=SEARCH_URL)) == []


def test_indeed_stops_at_max_results_via_while_condition() -> None:
    # A full page (jobs == page_size) with no tier total; the inner loop caps at
    # max_results, then the while condition ends the run.
    page = _mosaic_html(f"{_job_json('k1')},{_job_json('k2')}", tiers="[]")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=page)

    scraper = get_scraper("indeed", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(query_url=SEARCH_URL, config={"max_results": 2, "page_size": 2})
    )
    assert len(postings) == 2


def test_indeed_uses_tier_total_and_dedupes_across_pages() -> None:
    # Page one advertises a total of 3 jobs and returns 2 unique keys; page two
    # repeats one key (dedupe) plus a new one.
    page_one = _mosaic_html(f"{_job_json('k1')},{_job_json('k2')}", tiers='[{"jobCount":3}]')
    page_two = _mosaic_html(f"{_job_json('k2')},{_job_json('k3')}", tiers='[{"jobCount":3}]')

    def handler(request: httpx.Request) -> httpx.Response:
        if "start=2" in str(request.url):
            return httpx.Response(200, text=page_two)
        return httpx.Response(200, text=page_one)

    scraper = get_scraper("indeed", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(query_url=SEARCH_URL, config={"max_results": 10, "page_size": 2})
    )
    assert [p.external_id for p in postings] == ["k1", "k2", "k3"]


def test_indeed_rejects_non_indeed_host() -> None:
    scraper = get_scraper("indeed", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="requires an indeed.com search URL"):
        scraper.fetch(ScrapeContext(query_url="https://example.com/jobs?q=py"))


def test_indeed_rejects_non_jobs_path() -> None:
    scraper = get_scraper("indeed", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="must be a /jobs search page"):
        scraper.fetch(ScrapeContext(query_url="https://www.indeed.com/viewjob?jk=1"))


def test_indeed_config_needs_query_url_or_q_l() -> None:
    scraper = get_scraper("indeed", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="needs a query_url or config q/l"):
        scraper.fetch(ScrapeContext(config={"host": "www.indeed.com"}))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("max_results", "ten", "max_results must be a positive integer"),
        ("max_results", 0, "max_results must be a positive integer"),
        ("page_size", "ten", "page_size must be a positive integer"),
        ("page_size", 0, "page_size must be a positive integer"),
    ],
)
def test_indeed_rejects_bad_paging_config(field: str, value: object, message: str) -> None:
    scraper = get_scraper("indeed", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match=message):
        scraper.fetch(ScrapeContext(query_url=SEARCH_URL, config={field: value}))


def test_indeed_page_url_static_first_page_and_offset() -> None:
    assert IndeedScraper._page_url(SEARCH_URL, 0) == SEARCH_URL
    paged = IndeedScraper._page_url(SEARCH_URL, 10)
    assert "start=10" in paged
