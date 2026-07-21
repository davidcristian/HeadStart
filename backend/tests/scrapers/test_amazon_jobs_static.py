import pytest

from app.scrapers.adapters.amazon_jobs import AmazonJobsScraper


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


@pytest.mark.parametrize("hits", [float("inf"), float("nan"), float("-inf")])
def test_amazon_jobs_parse_response_nonfinite_hits_fallback(hits: float) -> None:
    """JSON Infinity/NaN hits must not raise OverflowError/ValueError."""
    jobs, count = AmazonJobsScraper._parse_response({"jobs": [{"id": "1"}], "hits": hits})
    assert count == 1
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
