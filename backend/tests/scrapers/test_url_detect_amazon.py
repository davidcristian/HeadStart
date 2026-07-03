"""Tests for Amazon Jobs URL detection."""

from app.scrapers.url_detect import detect_source_from_url


def test_detect_amazon_non_matching_host_returns_none() -> None:
    assert detect_source_from_url("https://jobs.example.com/en/search") is None


def test_detect_amazon_no_locale_prefix_defaults_to_en() -> None:
    result = detect_source_from_url("https://www.amazon.jobs/search?base_query=devops")
    assert result is not None
    assert result.adapter_key == "amazon_jobs"
    assert result.default_config["locale"] == "en"
    assert result.default_config["base_query"] == "devops"


def test_detect_amazon_no_query_uses_fallback_name() -> None:
    result = detect_source_from_url("https://amazon.jobs/de/search")
    assert result is not None
    assert result.default_config["locale"] == "de"
    assert result.suggested_name == "Amazon"
    assert "base_query" not in result.default_config
    assert "loc_query" not in result.default_config
    assert "country" not in result.default_config


def test_detect_amazon_blank_title_falls_back_to_parts() -> None:
    result = detect_source_from_url(
        "https://www.amazon.jobs/en/search?base_query=kernel&loc_query=Seattle",
        page_title="   ",
    )
    assert result is not None
    # Whitespace-only title strips to empty, so the name is built from parts.
    assert result.suggested_name == "Amazon / kernel / Seattle"
