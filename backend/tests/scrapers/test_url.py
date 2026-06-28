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
