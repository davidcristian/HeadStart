"""URL detection tests for the iCIMS / Jibe Attract scraper."""

from app.scrapers.url_detect import detect_source_from_url


def test_detect_icims_ignores_unrelated_careers_host() -> None:
    assert detect_source_from_url("https://careers.example.com/jobs") is None


def test_detect_icims_rivian_vanity_host() -> None:
    result = detect_source_from_url("https://careers.rivian.com/careers-home/jobs")
    assert result is not None
    assert result.adapter_key == "icims"
    assert result.base_url == "https://careers.rivian.com"
    assert result.default_config["company"] == "Rivian"
    assert result.default_config["careers_base_url"] == "https://careers.rivian.com"


def test_detect_icims_api_jobs_path() -> None:
    result = detect_source_from_url("https://careers.costco.com/api/jobs?limit=2")
    assert result is not None
    assert result.adapter_key == "icims"
    assert result.base_url == "https://careers.costco.com"
    assert result.default_config["careers_base_url"] == "https://careers.costco.com"


def test_detect_icims_jibeapply_host() -> None:
    result = detect_source_from_url("https://acme.jibeapply.com/jobs")
    assert result is not None
    assert result.adapter_key == "icims"
    assert result.base_url == "https://acme.jibeapply.com"
    assert result.default_config["company"] == "Acme"


def test_detect_icims_jibeapply_rejects_nested_host() -> None:
    assert detect_source_from_url("https://evil.acme.jibeapply.com/jobs") is None


def test_detect_icims_uses_page_title() -> None:
    result = detect_source_from_url(
        "https://careers.rivian.com/jobs",
        page_title="Rivian Automotive Careers",
    )
    assert result is not None
    assert result.suggested_name == "Rivian Automotive"
