"""Tests for job URL normalization."""

from app.scrapers.types import JobPosting
from app.scrapers.url import normalize_job_url, safe_http_job_url


def test_normalize_job_url_strips_trailing_slash_and_lowercases_host() -> None:
    assert normalize_job_url("HTTPS://Acme.Jobs/careers/123/") == "https://acme.jobs/careers/123"


def test_normalize_job_url_drops_tracking_query_params() -> None:
    assert (
        normalize_job_url("https://jobs.example.com/role?utm_source=newsletter&ref=home")
        == "https://jobs.example.com/role"
    )


def test_normalize_job_url_sorts_remaining_query_params() -> None:
    assert (
        normalize_job_url("https://jobs.example.com/role?team=eng&level=senior")
        == "https://jobs.example.com/role?level=senior&team=eng"
    )


def test_normalize_job_url_empty_returns_empty() -> None:
    assert normalize_job_url("   ") == ""


def test_normalize_job_url_relative_path_without_scheme_is_lowercased() -> None:
    assert normalize_job_url("Careers/123/") == "careers/123"


def test_normalize_job_url_strips_default_http_port() -> None:
    assert normalize_job_url("http://Acme.Jobs:80/careers/1") == "http://acme.jobs/careers/1"


def test_normalize_job_url_strips_default_https_port() -> None:
    assert normalize_job_url("https://Acme.Jobs:443/careers/1") == "https://acme.jobs/careers/1"


def test_safe_http_job_url_allows_http_https_only() -> None:
    assert safe_http_job_url("https://careers.example/jobs/1") == "https://careers.example/jobs/1"
    assert safe_http_job_url("  http://careers.example/jobs/1  ") == "http://careers.example/jobs/1"
    assert safe_http_job_url("javascript:alert(1)") is None
    assert safe_http_job_url("data:text/html,hi") is None
    assert safe_http_job_url("/relative") is None
    assert safe_http_job_url("https://") is None
    assert safe_http_job_url("") is None
    assert safe_http_job_url("   ") is None


def test_job_posting_url_clears_non_http_schemes_at_ingest() -> None:
    assert JobPosting(external_id="1", title="t", url="javascript:alert(1)").url == ""
    assert JobPosting(external_id="1", title="t", url="data:text/html,x").url == ""
    assert JobPosting(external_id="1", title="t", url="/relative").url == ""
    assert JobPosting(external_id="1", title="t", url="  ").url == ""
    assert (
        JobPosting(external_id="1", title="t", url="https://jobs.example/1").url
        == "https://jobs.example/1"
    )
    assert (
        JobPosting(external_id="1", title="t", url="  http://jobs.example/1  ").url
        == "http://jobs.example/1"
    )
