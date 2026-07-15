"""Tests for Microsoft Careers URL detection."""

from app.scrapers.url_detect import detect_source_from_url


def test_detect_microsoft_non_matching_host_returns_none() -> None:
    assert detect_source_from_url("https://careers.example.com/careers") is None


def test_detect_microsoft_rejects_lookalike_host_without_dot_boundary() -> None:
    """SCR-08: suffix match must require a dot before careers.microsoft.com."""
    assert detect_source_from_url("https://evilcareers.microsoft.com/careers") is None
    assert detect_source_from_url("https://xcareers.microsoft.com/api/pcsx/search") is None


def test_detect_microsoft_exact_careers_host_still_matches() -> None:
    result = detect_source_from_url("https://careers.microsoft.com/careers")
    assert result is not None
    assert result.adapter_key == "microsoft_careers"


def test_detect_microsoft_no_query_uses_fallback_name() -> None:
    result = detect_source_from_url("https://apply.careers.microsoft.com/careers")
    assert result is not None
    assert result.suggested_name == "Microsoft"
    assert "q" not in result.default_config
    assert "location" not in result.default_config


def test_detect_microsoft_api_without_domain_keeps_default() -> None:
    result = detect_source_from_url(
        "https://apply.careers.microsoft.com/api/pcsx/search?domain=&query=&location="
    )
    assert result is not None
    # Blank domain leaves the default in place; blank query/location are ignored.
    assert result.default_config["domain"] == "microsoft.com"
    assert "q" not in result.default_config
    assert "location" not in result.default_config


def test_detect_microsoft_api_with_location() -> None:
    result = detect_source_from_url(
        "https://apply.careers.microsoft.com/api/pcsx/search?query=kernel&location=Dublin"
    )
    assert result is not None
    assert result.default_config["q"] == "kernel"
    assert result.default_config["location"] == "Dublin"
    assert result.query_url.endswith("location=Dublin")


def test_detect_microsoft_blank_title_falls_back_to_parts() -> None:
    result = detect_source_from_url(
        "https://apply.careers.microsoft.com/careers?q=kernel&location=Redmond",
        page_title="   ",
    )
    assert result is not None
    # Whitespace-only title strips to empty, so the name is built from parts.
    assert result.suggested_name == "Microsoft / kernel / Redmond"
