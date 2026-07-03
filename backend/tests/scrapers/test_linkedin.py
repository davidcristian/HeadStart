"""Tests for the LinkedIn job-search scraper."""

import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from app.scrapers.adapters.linkedin import (
    LinkedInScraper,
    _flatten_query_params,
    _job_id_from_url,
    _normalize_job_url,
    _parse_cards,
)
from tests.conftest import load_fixture, make_http_client

SEARCH_URL = "https://www.linkedin.com/jobs/search/?keywords=python&location=remote"
GUEST_API_PREFIX = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"


def test_linkedin_parses_guest_api_cards() -> None:
    fixture = load_fixture("linkedin_search.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("linkedin", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(query_url=SEARCH_URL))

    assert seen["url"].startswith(GUEST_API_PREFIX)
    assert "keywords=python" in seen["url"]
    assert "location=remote" in seen["url"]
    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "4432008529"
    assert first.title == "Python Developer"
    assert first.company == "CGI"
    assert first.location == "Halifax, Nova Scotia, Canada"
    assert first.url == "https://www.linkedin.com/jobs/view/python-developer-at-cgi-4432008529"
    assert first.posted_at is not None
    assert postings[1].company == "Open Systems Technologies"


def test_linkedin_builds_guest_api_from_config() -> None:
    fixture = load_fixture("linkedin_search.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("linkedin", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(config={"keywords": "python", "location": "remote"}))

    assert "keywords=python" in seen["url"]
    assert "location=remote" in seen["url"]


def test_linkedin_paginates_with_start_offset() -> None:
    page_one = load_fixture("linkedin_search_paged.html")
    page_two = load_fixture("linkedin_search_page2.html")
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        if "start=2" in str(request.url):
            return httpx.Response(200, text=page_two)
        return httpx.Response(200, text=page_one)

    scraper = get_scraper("linkedin", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(query_url=SEARCH_URL, config={"max_results": 3, "page_size": 2})
    )

    assert len(urls) == 2
    assert "start=2" in urls[1]
    assert len(postings) == 3
    assert postings[-1].title == "Data Engineer"


def test_linkedin_preserves_search_filters_from_query_url() -> None:
    fixture = load_fixture("linkedin_search.html")
    seen: dict[str, str] = {}
    search_url = (
        "https://www.linkedin.com/jobs/search/?keywords=python&location=remote&f_TPR=r604800&f_WT=2"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("linkedin", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(query_url=search_url))

    assert "f_TPR=r604800" in seen["url"]
    assert "f_WT=2" in seen["url"]


def test_linkedin_rejects_auth_wall() -> None:
    auth_html = "<html><title>Sign in to LinkedIn</title><div class='authwall'></div></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=auth_html)

    scraper = get_scraper("linkedin", http=make_http_client(handler))
    try:
        scraper.fetch(ScrapeContext(query_url=SEARCH_URL))
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "auth wall" in str(exc)


def test_linkedin_stops_on_empty_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body></body></html>")

    scraper = get_scraper("linkedin", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(query_url=SEARCH_URL))

    assert postings == []


def test_linkedin_rejects_non_linkedin_host() -> None:
    scraper = get_scraper("linkedin", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="requires a linkedin.com search URL"):
        scraper.fetch(ScrapeContext(query_url="https://example.com/jobs/search/?keywords=py"))


def test_linkedin_rejects_non_search_path() -> None:
    scraper = get_scraper("linkedin", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="must be a /jobs/search page"):
        scraper.fetch(ScrapeContext(query_url="https://www.linkedin.com/jobs/view/123"))


def test_linkedin_query_url_without_keywords_or_location_raises() -> None:
    scraper = get_scraper("linkedin", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="must include keywords and/or location"):
        scraper.fetch(ScrapeContext(query_url="https://www.linkedin.com/jobs/search/?f_WT=2"))


def test_linkedin_config_needs_keywords_or_location() -> None:
    scraper = get_scraper("linkedin", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="needs a query_url or config keywords/location"):
        scraper.fetch(ScrapeContext(config={"max_results": 5}))


def test_linkedin_config_location_only() -> None:
    fixture = load_fixture("linkedin_search.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("linkedin", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(config={"location": "remote"}))

    assert "location=remote" in seen["url"]
    assert "keywords" not in seen["url"]


def test_linkedin_config_keywords_and_filters() -> None:
    fixture = load_fixture("linkedin_search.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("linkedin", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(config={"keywords": "python", "geoId": "123", "f_TPR": "", "f_WT": None})
    )

    assert "keywords=python" in seen["url"]
    assert "geoId=123" in seen["url"]
    # Blank/None filters are dropped.
    assert "f_TPR" not in seen["url"]
    assert "f_WT" not in seen["url"]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("max_results", "ten", "max_results must be a positive integer"),
        ("max_results", 0, "max_results must be a positive integer"),
        ("max_results", True, "max_results must be a positive integer"),
        ("page_size", "ten", "page_size must be a positive integer"),
        ("page_size", 0, "page_size must be a positive integer"),
        ("page_size", True, "page_size must be a positive integer"),
    ],
)
def test_linkedin_rejects_bad_paging_config(field: str, value: object, message: str) -> None:
    scraper = get_scraper("linkedin", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match=message):
        scraper.fetch(ScrapeContext(query_url=SEARCH_URL, config={field: value}))


def test_linkedin_guest_page_url_first_page_drops_start() -> None:
    # A search_params dict that already carries "start" must have it removed on
    # the first page (offset 0).
    url = LinkedInScraper._guest_page_url({"keywords": "py", "start": "50"}, 0)
    assert "start" not in url


def test_linkedin_guest_page_url_no_params() -> None:
    assert LinkedInScraper._guest_page_url({}, 0) == GUEST_API_PREFIX


def test_linkedin_flatten_query_params_drops_start_and_empty() -> None:
    flat = _flatten_query_params({"start": ["10"], "keywords": ["py"], "location": []})
    assert flat == {"keywords": "py"}


def test_linkedin_job_id_from_url_no_match() -> None:
    assert _job_id_from_url("https://www.linkedin.com/jobs/view/no-id-here") == ""


def test_linkedin_normalize_job_url_falls_back_to_view_url() -> None:
    # A relative/invalid href (no scheme+netloc) falls back to the canonical view URL.
    assert _normalize_job_url("/relative/path", "42") == "https://www.linkedin.com/jobs/view/42"
    assert _normalize_job_url("", "42") == "https://www.linkedin.com/jobs/view/42"


def test_linkedin_card_derives_id_from_href_when_urn_missing() -> None:
    html = """
    <div class="job-search-card">
      <a class="base-card__full-link"
         href="https://www.linkedin.com/jobs/view/data-engineer-at-acme-987654321?foo=1">
        <span class="sr-only">Data Engineer</span>
      </a>
      <h3 class="base-search-card__title">Data Engineer</h3>
    </div>
    """
    postings = _parse_cards(html)
    assert len(postings) == 1
    assert postings[0].external_id == "987654321"


def test_linkedin_card_skipped_when_missing_id_and_title() -> None:
    # No urn, href without an id, and no title node -> card dropped.
    html = """
    <div class="job-search-card">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/no-id"></a>
    </div>
    """
    assert _parse_cards(html) == []


def test_linkedin_card_without_time_node() -> None:
    html = """
    <div class="job-search-card" data-entity-urn="urn:li:jobPosting:111">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/x-111"></a>
      <h3 class="base-search-card__title">Role</h3>
    </div>
    """
    postings = _parse_cards(html)
    assert postings[0].posted_at is None


def test_linkedin_card_with_blank_and_bad_datetime() -> None:
    html = """
    <div class="job-search-card" data-entity-urn="urn:li:jobPosting:222">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/x-222"></a>
      <h3 class="base-search-card__title">Blank Date</h3>
      <time class="job-search-card__listdate" datetime="  "></time>
    </div>
    <div class="job-search-card" data-entity-urn="urn:li:jobPosting:333">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/x-333"></a>
      <h3 class="base-search-card__title">Bad Date</h3>
      <time class="job-search-card__listdate" datetime="not-a-date"></time>
    </div>
    """
    postings = _parse_cards(html)
    assert postings[0].posted_at is None
    assert postings[1].posted_at is None
