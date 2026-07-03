"""Tests for Apple Careers URL detection."""

from app.scrapers.url_detect import detect_source_from_url


def test_detect_apple_non_matching_host_returns_none() -> None:
    assert detect_source_from_url("https://careers.example.com/en-us/search") is None


def test_detect_apple_no_locale_prefix_defaults_to_en_us() -> None:
    result = detect_source_from_url("https://jobs.apple.com/search?search=swift")
    assert result is not None
    assert result.adapter_key == "apple_careers"
    assert result.default_config["locale"] == "en-us"
    assert result.default_config["search"] == "swift"
    # Path does not end in /search after rstrip? It does, so query_url is the geturl.
    assert result.query_url == "https://jobs.apple.com/search?search=swift"


def test_detect_apple_non_search_path_uses_base_query_url() -> None:
    result = detect_source_from_url("https://jobs.apple.com/en-us/teams")
    assert result is not None
    assert result.query_url == "https://jobs.apple.com/en-us/search"


def test_detect_apple_no_query_uses_fallback_name() -> None:
    result = detect_source_from_url("https://jobs.apple.com/en-us/search")
    assert result is not None
    assert result.suggested_name == "Apple"
    assert "search" not in result.default_config
    assert "location" not in result.default_config


def test_detect_apple_blank_title_falls_back_to_parts() -> None:
    result = detect_source_from_url(
        "https://jobs.apple.com/en-us/search?search=swift&location=cupertino",
        page_title="   ",
    )
    assert result is not None
    # Whitespace-only title strips to empty, so the name is built from parts.
    assert result.suggested_name == "Apple / swift / cupertino"
