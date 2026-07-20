"""URL detection tests for the Phenom People scraper."""

from __future__ import annotations

from app.scrapers.url_detect import detect_source_from_url


def test_detect_phenom_ignores_unrelated_careers_host() -> None:
    assert detect_source_from_url("https://careers.example.com/jobs") is None


def test_detect_phenom_cisco_host() -> None:
    result = detect_source_from_url("https://careers.cisco.com/global/en/search-results")
    assert result is not None
    assert result.adapter_key == "phenom"
    assert result.base_url == "https://careers.cisco.com"
    assert result.default_config["ref_num"] == "CISCISGLOBAL"
    assert result.default_config["company"] == "Cisco"
    assert result.default_config["country"] == "global"
    assert result.default_config["locale"] == "en_global"


def test_detect_phenom_cisco_splunk_path_sets_keywords() -> None:
    result = detect_source_from_url("https://careers.cisco.com/global/en/splunk")
    assert result is not None
    assert result.adapter_key == "phenom"
    assert result.default_config["company"] == "Splunk"
    assert result.default_config["keywords"] == "Splunk"


def test_detect_phenom_widgets_path() -> None:
    result = detect_source_from_url("https://jobs.examplecorp.com/widgets")
    assert result is not None
    assert result.adapter_key == "phenom"
    assert result.base_url == "https://jobs.examplecorp.com"
    assert result.default_config["careers_base_url"] == "https://jobs.examplecorp.com"


def test_detect_phenom_uses_page_title() -> None:
    result = detect_source_from_url(
        "https://careers.cisco.com/global/en/search-results",
        page_title="Cisco Careers",
    )
    assert result is not None
    assert result.suggested_name == "Cisco"
