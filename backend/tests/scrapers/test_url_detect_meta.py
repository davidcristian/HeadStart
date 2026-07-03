"""Tests for Meta Careers URL detection."""

from app.scrapers.url_detect import detect_source_from_url


def test_detect_meta_non_matching_host_returns_none() -> None:
    assert detect_source_from_url("https://careers.example.com/jobs") is None


def test_detect_meta_job_detail_path_returns_none() -> None:
    assert detect_source_from_url("https://www.metacareers.com/jobs/123456789/") is None


def test_detect_meta_no_query_uses_fallback_name() -> None:
    result = detect_source_from_url("https://www.metacareers.com/jobs")
    assert result is not None
    assert result.suggested_name == "Meta"
    assert "q" not in result.default_config


def test_detect_meta_blank_title_falls_back_to_parts() -> None:
    result = detect_source_from_url(
        "https://www.metacareers.com/jobsearch/?q=infra",
        page_title="   ",
    )
    assert result is not None
    # Whitespace-only title strips to empty, so the name is built from parts.
    assert result.suggested_name == "Meta / infra"
