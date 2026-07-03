"""Tests for SmartRecruiters URL detection."""

from app.scrapers.url_detect import detect_source_from_url


def test_detect_smartrecruiters_non_matching_host_returns_none() -> None:
    assert detect_source_from_url("https://careers.example.com/Atlassian") is None


def test_detect_smartrecruiters_careers_no_company_returns_none() -> None:
    assert detect_source_from_url("https://careers.smartrecruiters.com/") is None


def test_detect_smartrecruiters_jobs_host() -> None:
    result = detect_source_from_url("https://jobs.smartrecruiters.com/Atlassian")
    assert result is not None
    assert result.default_config["company_id"] == "Atlassian"


def test_detect_smartrecruiters_api_wrong_path_returns_none() -> None:
    assert detect_source_from_url("https://api.smartrecruiters.com/v1/other/AcmeCorp") is None


def test_detect_smartrecruiters_suffix_stripped_title() -> None:
    result = detect_source_from_url(
        "https://careers.smartrecruiters.com/acme-corp",
        page_title="Acme Corp Careers",
    )
    assert result is not None
    # The " Careers" suffix is stripped from the page title.
    assert result.suggested_name == "Acme Corp"


def test_detect_smartrecruiters_blank_title_uses_humanized_slug() -> None:
    result = detect_source_from_url(
        "https://careers.smartrecruiters.com/acme-corp",
        page_title="   ",
    )
    assert result is not None
    # Whitespace-only title strips to empty, so the humanized slug is used.
    assert result.suggested_name == "Acme Corp"
