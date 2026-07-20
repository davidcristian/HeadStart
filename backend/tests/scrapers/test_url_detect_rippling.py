"""URL detection tests for the Rippling ATS scraper."""

from app.scrapers.url_detect import detect_source_from_url


def test_detect_rippling_ignores_unrelated_host() -> None:
    assert detect_source_from_url("https://careers.example.com/jobs") is None


def test_detect_rippling_ats_board_url() -> None:
    result = detect_source_from_url("https://ats.rippling.com/petfolk/jobs")
    assert result is not None
    assert result.adapter_key == "rippling"
    assert result.base_url == "https://ats.rippling.com/petfolk"
    assert result.default_config["board"] == "petfolk"
    assert result.default_config["company"] == "Petfolk"


def test_detect_rippling_api_url() -> None:
    result = detect_source_from_url(
        "https://api.rippling.com/platform/api/ats/v1/board/rippling/jobs"
    )
    assert result is not None
    assert result.adapter_key == "rippling"
    assert result.default_config["board"] == "rippling"
    assert result.base_url == "https://ats.rippling.com/rippling"


def test_detect_rippling_rejects_invalid_board_slug() -> None:
    assert detect_source_from_url("https://ats.rippling.com/evil.board/jobs") is None
    assert detect_source_from_url("https://ats.rippling.com/-bad/jobs") is None
    assert (
        detect_source_from_url("https://api.rippling.com/platform/api/ats/v1/board/evil.board/jobs")
        is None
    )
    assert detect_source_from_url("https://api.rippling.com/platform/api/ats/v1/jobs") is None


def test_detect_rippling_uses_page_title() -> None:
    result = detect_source_from_url(
        "https://ats.rippling.com/rippling/jobs",
        page_title="Rippling Careers",
    )
    assert result is not None
    assert result.suggested_name == "Rippling"


def test_detect_rippling_page_title_without_suffix() -> None:
    result = detect_source_from_url(
        "https://ats.rippling.com/acme/jobs",
        page_title="Acme Corp",
    )
    assert result is not None
    assert result.suggested_name == "Acme Corp"
