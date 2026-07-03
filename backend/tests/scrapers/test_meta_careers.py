import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client


def test_meta_careers_parses_postings() -> None:
    page_fixture = load_fixture("meta_careers_page.html")
    search_fixture = load_fixture("meta_careers_search.json")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.method == "GET":
            return httpx.Response(200, text=page_fixture)
        assert request.method == "POST"
        assert str(request.url).endswith("/graphql")
        assert request.headers.get("x-fb-lsd") == "test_lsd_token"
        assert request.headers.get("x-fb-friendly-name") == "CareersJobSearchResultsDataQuery"
        body = request.content.decode()
        assert "test_lsd_token" in body
        assert "software" in body
        return httpx.Response(
            200,
            text=search_fixture,
            headers={"content-type": "application/json"},
        )

    scraper = get_scraper("meta_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://www.metacareers.com/jobsearch/?q=software",
            config={"company": "Meta"},
        )
    )

    assert len(calls) == 2
    assert calls[0].endswith("/jobsearch/?q=software")
    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "2132019417725760"
    assert first.title == "Technical Program Manager, MTIA Software"
    assert first.company == "Meta"
    assert first.location == "Menlo Park, CA"
    assert first.url == "https://www.metacareers.com/jobs/2132019417725760/"
    assert first.content_hash() != postings[1].content_hash()


def test_meta_careers_builds_search_from_config() -> None:
    page_fixture = load_fixture("meta_careers_page.html")
    search_fixture = load_fixture("meta_careers_search.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            seen["page_url"] = str(request.url)
            return httpx.Response(200, text=page_fixture)
        seen["graphql_body"] = request.content.decode()
        return httpx.Response(200, text=search_fixture)

    scraper = get_scraper("meta_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            config={"q": "platform", "company": "Meta"},
        )
    )

    assert seen["page_url"].endswith("/jobsearch/?q=platform")
    assert "platform" in seen["graphql_body"]


def test_meta_careers_reads_keyword_from_filters() -> None:
    page_fixture = load_fixture("meta_careers_page.html")
    search_fixture = load_fixture("meta_careers_search.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=page_fixture)
        seen["graphql_body"] = request.content.decode()
        return httpx.Response(200, text=search_fixture)

    scraper = get_scraper("meta_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            filters={"keywords_include": "kernel"},
            config={"company": "Meta"},
        )
    )

    assert "kernel" in seen["graphql_body"]


def test_meta_careers_respects_max_results() -> None:
    page_fixture = load_fixture("meta_careers_page.html")
    search_fixture = load_fixture("meta_careers_search.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=page_fixture)
        return httpx.Response(200, text=search_fixture)

    scraper = get_scraper("meta_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            config={"company": "Meta", "max_results": 1},
        )
    )

    assert len(postings) == 1


def _noop_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text="")


def test_meta_careers_rejects_non_metacareers_host() -> None:
    scraper = get_scraper("meta_careers", http=make_http_client(_noop_handler))
    with pytest.raises(ValueError, match="requires a metacareers.com URL"):
        scraper.fetch(ScrapeContext(query_url="https://example.com/jobsearch/"))


def test_meta_careers_rejects_job_posting_url() -> None:
    scraper = get_scraper("meta_careers", http=make_http_client(_noop_handler))
    with pytest.raises(ValueError, match="not a posting"):
        scraper.fetch(ScrapeContext(query_url="https://www.metacareers.com/jobs/12345/"))


def test_meta_careers_rejects_non_search_path() -> None:
    scraper = get_scraper("meta_careers", http=make_http_client(_noop_handler))
    with pytest.raises(ValueError, match="must be a job search page"):
        scraper.fetch(ScrapeContext(query_url="https://www.metacareers.com/about"))


def test_meta_careers_reads_keyword_from_query_url() -> None:
    page_fixture = load_fixture("meta_careers_page.html")
    search_fixture = load_fixture("meta_careers_search.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=page_fixture)
        seen["graphql_body"] = request.content.decode()
        return httpx.Response(200, text=search_fixture)

    scraper = get_scraper("meta_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://www.metacareers.com/jobsearch/?q=distributed",
            config={"company": "Meta"},
        )
    )

    assert "distributed" in seen["graphql_body"]


def test_meta_careers_query_url_blank_keyword_falls_through() -> None:
    # A blank ``q`` param forces the query-url keyword loop to skip and fall
    # through to config-based keyword resolution.
    page_fixture = load_fixture("meta_careers_page.html")
    search_fixture = load_fixture("meta_careers_search.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=page_fixture)
        seen["graphql_body"] = request.content.decode()
        return httpx.Response(200, text=search_fixture)

    scraper = get_scraper("meta_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url="https://www.metacareers.com/jobsearch/?q=",
            config={"company": "Meta", "q": "backend"},
        )
    )

    assert "backend" in seen["graphql_body"]


def test_meta_careers_rejects_non_numeric_max_results() -> None:
    scraper = get_scraper("meta_careers", http=make_http_client(_noop_handler))
    with pytest.raises(ValueError, match="max_results must be a positive integer"):
        scraper.fetch(ScrapeContext(config={"max_results": "lots"}))


def test_meta_careers_rejects_non_positive_max_results() -> None:
    scraper = get_scraper("meta_careers", http=make_http_client(_noop_handler))
    with pytest.raises(ValueError, match="max_results must be a positive integer"):
        scraper.fetch(ScrapeContext(config={"max_results": 0}))
