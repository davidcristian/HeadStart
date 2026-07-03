"""Tests for Uber Careers URL detection."""

from app.scrapers.url_detect import detect_source_from_url


def test_detect_uber_non_matching_host_returns_none() -> None:
    assert detect_source_from_url("https://careers.example.com/careers") is None


def test_detect_uber_non_careers_path_returns_none() -> None:
    assert detect_source_from_url("https://www.uber.com/us/en/about/") is None


def test_detect_uber_careers_no_locale_prefix() -> None:
    result = detect_source_from_url("https://www.uber.com/careers/")
    assert result is not None
    assert result.adapter_key == "uber_careers"
    # No locale segments in the path, so the default locale path is used.
    assert result.default_config["careers_locale_path"] == "us/en"
    assert result.base_url == "https://www.uber.com/us/en/careers/list/"


def test_detect_uber_page_title_stripped() -> None:
    result = detect_source_from_url(
        "https://www.uber.com/us/en/careers/list/",
        page_title="Engineering | Uber Careers",
    )
    assert result is not None
    assert result.suggested_name == "Engineering"


def test_detect_uber_blank_title_falls_back() -> None:
    result = detect_source_from_url(
        "https://www.uber.com/us/en/careers/list/",
        page_title="   ",
    )
    assert result is not None
    # Whitespace-only title strips to empty, so the default name is used.
    assert result.suggested_name == "Uber Careers"
