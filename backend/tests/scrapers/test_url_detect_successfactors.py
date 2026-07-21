"""URL detection tests for SuccessFactors Career Site Builder boards."""

from app.scrapers.url_detect import detect_source_from_url


def test_detect_successfactors_ignores_unrelated_host() -> None:
    assert detect_source_from_url("https://example.com/careers") is None


def test_detect_successfactors_cloud_host() -> None:
    result = detect_source_from_url("https://acme.jobs.hr.cloud.sap/")
    assert result is not None
    assert result.adapter_key == "successfactors"
    assert result.default_config["careers_base_url"] == "https://acme.jobs.hr.cloud.sap"
    assert result.default_config["company"] == "Acme"
    assert result.query_url == "https://acme.jobs.hr.cloud.sap"


def test_detect_successfactors_known_wlgore() -> None:
    result = detect_source_from_url("https://wlgore.jobs.hr.cloud.sap/go/All-Jobs/9813400/")
    assert result is not None
    assert result.adapter_key == "successfactors"
    assert result.default_config["company"] == "W. L. Gore & Associates"
    assert result.default_config["portal_id"] == "wlgore"


def test_detect_successfactors_jobs_api_path() -> None:
    result = detect_source_from_url(
        "https://careers.example.com/services/recruiting/v1/jobs"
    )
    assert result is not None
    assert result.adapter_key == "successfactors"
    assert result.default_config["careers_base_url"] == "https://careers.example.com"


def test_detect_successfactors_rejects_bare_cloud_root() -> None:
    assert detect_source_from_url("https://jobs.hr.cloud.sap/") is None


def test_detect_successfactors_uses_page_title() -> None:
    result = detect_source_from_url(
        "https://acme.jobs.hr.cloud.sap/",
        page_title="Acme Careers",
    )
    assert result is not None
    assert result.suggested_name == "Acme"


def test_detect_successfactors_blank_title_falls_back() -> None:
    result = detect_source_from_url(
        "https://acme.jobs.hr.cloud.sap/",
        page_title="   ",
    )
    assert result is not None
    assert result.suggested_name == "Acme"
