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


def test_detect_phenom_cvs_health_host() -> None:
    result = detect_source_from_url("https://jobs.cvshealth.com/us/en/search-results")
    assert result is not None
    assert result.adapter_key == "phenom"
    assert result.default_config["company"] == "CVS Health"
    assert result.default_config["ref_num"] == "CVSCHLUS"
    assert result.default_config["country"] == "us"
    assert result.default_config["locale"] == "en_us"


def test_detect_phenom_ge_healthcare_host() -> None:
    result = detect_source_from_url("https://careers.gehealthcare.com/global/en/search-results")
    assert result is not None
    assert result.adapter_key == "phenom"
    assert result.default_config["company"] == "GE HealthCare"
    assert result.default_config["ref_num"] == "GEVGHLGLOBAL"


def test_detect_phenom_rtx_host() -> None:
    result = detect_source_from_url("https://careers.rtx.com/global/en/search-results")
    assert result is not None
    assert result.adapter_key == "phenom"
    assert result.default_config["company"] == "RTX"
    assert result.default_config["ref_num"] == "RAYTGLOBAL"
