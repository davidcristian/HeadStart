"""Tests for Shopify Careers URL detection."""

from app.scrapers.url_detect import detect_source_from_url


def test_detect_shopify_non_matching_host_returns_none() -> None:
    assert detect_source_from_url("https://careers.example.com/careers") is None


def test_detect_shopify_blank_title_falls_back_to_keyword() -> None:
    result = detect_source_from_url(
        "https://www.shopify.com/careers?q=engineer",
        page_title="   ",
    )
    assert result is not None
    # Whitespace-only title strips to empty, so the keyword fallback is used.
    assert result.suggested_name == "Shopify / engineer"


def test_detect_shopify_blank_title_no_keyword_falls_back() -> None:
    result = detect_source_from_url(
        "https://www.shopify.com/careers",
        page_title="   ",
    )
    assert result is not None
    assert result.suggested_name == "Shopify Careers"
