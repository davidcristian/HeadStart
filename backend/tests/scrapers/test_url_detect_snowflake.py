"""Tests for Snowflake Careers URL detection."""

from app.scrapers.url_detect import detect_source_from_url


def test_detect_snowflake_non_matching_host_returns_none() -> None:
    assert detect_source_from_url("https://careers.example.com/us/en/search-results") is None


def test_detect_snowflake_root_path() -> None:
    result = detect_source_from_url("https://careers.snowflake.com/")
    assert result is not None
    assert result.adapter_key == "snowflake_careers"
    assert result.default_config["portal_id"] == "snowflake"


def test_detect_snowflake_search_results_no_locale_prefix() -> None:
    result = detect_source_from_url("https://careers.snowflake.com/search-results")
    assert result is not None
    assert result.adapter_key == "snowflake_careers"


def test_detect_snowflake_page_title_stripped() -> None:
    result = detect_source_from_url(
        "https://careers.snowflake.com/us/en/search-results",
        page_title="Engineering | Snowflake Careers",
    )
    assert result is not None
    assert result.suggested_name == "Engineering"


def test_detect_snowflake_blank_title_falls_back_to_keyword() -> None:
    result = detect_source_from_url(
        "https://careers.snowflake.com/us/en/search-results?q=data",
        page_title="   ",
    )
    assert result is not None
    # Whitespace-only title strips to empty, so the keyword fallback is used.
    assert result.suggested_name == "Snowflake / data"
