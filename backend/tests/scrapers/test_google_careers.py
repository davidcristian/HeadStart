import httpx

from app.scrapers import ScrapeContext, get_scraper
from app.scrapers.adapters.google_careers_parse import parse_search_page
from tests.conftest import load_fixture, make_http_client


def test_google_careers_tolerates_malformed_json_blob() -> None:
    """A balanced-but-invalid embedded JSON blob must yield no postings, not crash."""
    html = "noise AF_initDataCallback({key: 'ds:1', data:[abc] });"
    postings = parse_search_page(
        html, company="Google", applications_base="https://careers.google.com", query_params={}
    )
    assert postings == []


def test_google_careers_parses_postings() -> None:
    fixture = load_fixture("google_careers_results.html")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/jobs/results/" in str(request.url)
        assert request.url.params.get("page") == "1"
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("google_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://www.google.com/about/careers/applications/jobs/results/?q=software",
            config={"company": "Google"},
        )
    )

    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "72271215732892358"
    assert first.title == "Software Engineer, Mobile (iOS), Google Photos"
    assert first.company == "Google"
    assert first.location == "Sydney NSW, Australia"
    assert (
        first.url == "https://www.google.com/about/careers/applications/jobs/results/"
        "72271215732892358-software-engineer-mobile-ios-google-photos?q=software"
    )
    assert first.posted_at is not None
    assert first.content_hash() != postings[1].content_hash()


def test_google_careers_builds_search_from_config() -> None:
    fixture = load_fixture("google_careers_results.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("google_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            config={"q": "software", "location": "United States", "company": "Google"},
        )
    )

    assert "q=software" in seen["url"]
    assert "location=United+States" in seen["url"]


def test_google_careers_reads_keyword_from_filters() -> None:
    fixture = load_fixture("google_careers_results.html")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("google_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            filters={"keywords_include": "platform"},
            config={"company": "Google"},
        )
    )

    assert "q=platform" in seen["url"]


def test_google_careers_paginates_until_short_page() -> None:
    fixture = load_fixture("google_careers_results.html")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url.params.get("page")))
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("google_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://www.google.com/about/careers/applications/jobs/results/?q=software",
            config={"company": "Google", "max_results": 50},
        )
    )

    assert len(postings) == 2
    assert calls == ["1"]
