import json

import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from app.scrapers.adapters.amazon_jobs import AmazonJobsScraper
from tests.conftest import load_fixture, make_http_client


def test_amazon_jobs_parses_postings() -> None:
    fixture = load_fixture("amazon_jobs_search.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/en/search.json" in str(request.url)
        assert request.url.params["base_query"] == "software"
        assert request.url.params["offset"] == "0"
        return httpx.Response(200, text=fixture, headers={"content-type": "application/json"})

    scraper = get_scraper("amazon_jobs", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://www.amazon.jobs/en/search?base_query=software",
            config={"company": "Amazon"},
        )
    )

    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "10410605"
    assert first.title == "Software Development Manager, Flight Software"
    assert first.company == "Amazon Kuiper Manufacturing Enterprises LLC"
    assert first.location == "Redmond, Washington, USA"
    assert (
        first.url
        == "https://www.amazon.jobs/en/jobs/10410605/software-development-manager-flight-software"
    )
    assert first.posted_at is not None
    assert first.content_hash() != postings[1].content_hash()


def test_amazon_jobs_builds_search_from_config() -> None:
    fixture = load_fixture("amazon_jobs_search.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("amazon_jobs", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            config={
                "q": "platform",
                "location": "Seattle",
                "country": "USA",
                "company": "Amazon",
            },
        )
    )

    assert "base_query=platform" in seen["url"]
    assert "loc_query=Seattle" in seen["url"]
    assert "country=USA" in seen["url"]


def test_amazon_jobs_reads_keyword_from_filters() -> None:
    fixture = load_fixture("amazon_jobs_search.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("amazon_jobs", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            filters={"keywords_include": "kernel"},
            config={"company": "Amazon"},
        )
    )

    assert "base_query=kernel" in seen["url"]


def test_amazon_jobs_paginates_until_short_page() -> None:
    fixture = load_fixture("amazon_jobs_search.json")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url.params.get("offset")))
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("amazon_jobs", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            config={"company": "Amazon", "q": "software", "max_results": 50},
        )
    )

    assert len(postings) == 2
    assert calls == ["0"]


def _payload(jobs: list[dict], *, hits: int | None = None) -> str:
    body: dict = {"jobs": jobs}
    if hits is not None:
        body["hits"] = hits
    return json.dumps(body)


def test_amazon_jobs_passes_all_location_params() -> None:
    """region and city config values reach the query string (lines 68, 70)."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=_payload([]))

    scraper = get_scraper("amazon_jobs", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            config={
                "q": "software",
                "loc_query": "Seattle",
                "country": "USA",
                "region": "WA",
                "city": "Seattle",
            },
        )
    )

    assert "country=USA" in seen["url"]
    assert "region=WA" in seen["url"]
    assert "city=Seattle" in seen["url"]


def test_amazon_jobs_empty_page_stops() -> None:
    """An empty jobs array breaks the loop immediately (line 78)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_payload([], hits=0))

    scraper = get_scraper("amazon_jobs", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"q": "nothing"}))

    assert postings == []


def test_amazon_jobs_dedupes_and_stops_at_max_results() -> None:
    """Duplicate ids are skipped (line 82) and max_results caps the inner loop (line 86)."""
    jobs = [
        {"id_icims": "1", "title": "A", "job_path": "/en/jobs/1/a"},
        {"id_icims": "1", "title": "A dup", "job_path": "/en/jobs/1/a"},
        {"id_icims": "2", "title": "B", "job_path": "/en/jobs/2/b"},
        {"id_icims": "3", "title": "C", "job_path": "/en/jobs/3/c"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_payload(jobs, hits=100))

    scraper = get_scraper("amazon_jobs", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"q": "software", "max_results": 2}))

    assert [p.external_id for p in postings] == ["1", "2"]


def test_amazon_jobs_paginates_multiple_pages_then_reaches_total() -> None:
    """Full pages keep looping (90->55, 75->77) then offset >= total stops (line 89)."""
    page1 = [
        {"id_icims": str(i), "title": f"J{i}", "job_path": f"/en/jobs/{i}/j"} for i in range(1, 101)
    ]
    page2 = [
        {"id_icims": str(i), "title": f"J{i}", "job_path": f"/en/jobs/{i}/j"}
        for i in range(101, 201)
    ]
    offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = request.url.params.get("offset")
        offsets.append(offset)
        jobs = page1 if offset == "0" else page2
        return httpx.Response(200, text=_payload(jobs, hits=200))

    scraper = get_scraper("amazon_jobs", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"q": "software", "max_results": 500}))

    assert len(postings) == 200
    assert offsets == ["0", "100"]


def test_amazon_jobs_loop_condition_false_after_full_page() -> None:
    """A full page reaching max_results re-checks the while and exits (55->93)."""
    jobs = [
        {"id_icims": str(i), "title": f"J{i}", "job_path": f"/en/jobs/{i}/j"} for i in range(1, 101)
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_payload(jobs, hits=500))

    scraper = get_scraper("amazon_jobs", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"q": "software", "max_results": 100}))

    assert len(postings) == 100


def test_amazon_jobs_no_keyword_omits_base_query() -> None:
    """With no keyword the base_query param is omitted (61->63)."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=_payload([]))

    scraper = get_scraper("amazon_jobs", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(config={"company": "Amazon"}))

    assert "base_query=" not in seen["url"]


def test_amazon_jobs_rejects_non_amazon_url() -> None:
    """A non-amazon.jobs host raises (line 109)."""
    scraper = get_scraper("amazon_jobs", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="amazon.jobs URL"):
        scraper.fetch(ScrapeContext(query_url="https://example.com/jobs"))


def test_amazon_jobs_url_without_locale_or_search_path() -> None:
    """A bare amazon.jobs root URL: no locale match (112->115), no search path (116->124)."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=_payload([]))

    scraper = get_scraper("amazon_jobs", http=make_http_client(handler))
    scraper.fetch(ScrapeContext(query_url="https://www.amazon.jobs/", config={"q": "fallback"}))

    # locale defaults to "en", keyword falls back to config value
    assert "/en/search.json" in seen["url"]
    assert "base_query=fallback" in seen["url"]


@pytest.mark.parametrize("bad", ["nope", 0, -5, True])
def test_amazon_jobs_page_size_validation(bad: object) -> None:
    """page_size must be a positive non-bool number (lines 171, 174)."""
    with pytest.raises(ValueError, match="page_size must be a positive integer"):
        AmazonJobsScraper._page_size({"page_size": bad})


@pytest.mark.parametrize("bad", ["nope", 0, -5, True])
def test_amazon_jobs_max_results_validation(bad: object) -> None:
    """max_results must be a positive non-bool number (lines 181, 184)."""
    with pytest.raises(ValueError, match="max_results must be a positive integer"):
        AmazonJobsScraper._max_results({"max_results": bad})


def test_amazon_jobs_parse_response_rejects_non_object() -> None:
    """A non-dict payload raises (line 190)."""
    with pytest.raises(ValueError, match="expected object"):
        AmazonJobsScraper._parse_response([1, 2, 3])


def test_amazon_jobs_parse_response_rejects_non_array_jobs() -> None:
    """A non-list jobs field raises (line 193)."""
    with pytest.raises(ValueError, match="expected array"):
        AmazonJobsScraper._parse_response({"jobs": "oops"})


def test_amazon_jobs_parse_response_hits_fallback_to_len() -> None:
    """Missing/invalid hits falls back to len(jobs) and non-dicts are filtered."""
    jobs, count = AmazonJobsScraper._parse_response(
        {"jobs": [{"id": "1"}, "skip"], "hits": "not-a-number"}
    )
    assert count == 2
    assert jobs == [{"id": "1"}]


def test_amazon_jobs_to_posting_requires_id() -> None:
    """A job without an id raises (line 202)."""
    with pytest.raises(ValueError, match="missing id"):
        AmazonJobsScraper._to_posting({"title": "no id"}, company="Amazon")


def test_amazon_jobs_format_location_falls_back_to_location() -> None:
    """Empty normalized_location falls through to raw location (line 223)."""
    assert AmazonJobsScraper._format_location({"location": "US, WA"}) == "US, WA"


def test_amazon_jobs_job_url_builds_from_id_when_path_missing() -> None:
    """No job_path builds the canonical path from the id (lines 229-231)."""
    assert AmazonJobsScraper._job_url({"id_icims": "42"}) == "https://www.amazon.jobs/en/jobs/42"


def test_amazon_jobs_job_url_absolute_passthrough() -> None:
    """An absolute job_path is returned unchanged (line 233)."""
    url = "https://www.amazon.jobs/en/jobs/99/x"
    assert AmazonJobsScraper._job_url({"job_path": url}) == url


def test_amazon_jobs_job_url_relative_without_slash() -> None:
    """A relative job_path lacking a leading slash gets one (line 236)."""
    assert (
        AmazonJobsScraper._job_url({"job_path": "en/jobs/1/x"})
        == "https://www.amazon.jobs/en/jobs/1/x"
    )


def test_amazon_jobs_job_url_empty_returns_origin() -> None:
    """No id and no path returns the bare origin (line 236 else branch)."""
    assert AmazonJobsScraper._job_url({}) == "https://www.amazon.jobs"


def test_amazon_jobs_posted_at_missing_returns_none() -> None:
    """No posted_date returns None (line 242)."""
    assert AmazonJobsScraper._posted_at({}) is None


def test_amazon_jobs_posted_at_unparseable_returns_none() -> None:
    """A posted_date that fails the regex returns None (line 246)."""
    assert AmazonJobsScraper._posted_at({"posted_date": "yesterday"}) is None


def test_amazon_jobs_posted_at_invalid_month_returns_none() -> None:
    """A regex-matching but invalid month returns None via strptime (lines 249-250)."""
    assert AmazonJobsScraper._posted_at({"posted_date": "Foobar 4, 2026"}) is None
