"""Tests for job URL normalization."""

from app.scrapers.url import normalize_job_url


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
