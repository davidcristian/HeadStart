"""Tests for compensation display formatting and Ashby structured extraction."""

from app.scrapers.types import JobPosting
from app.services.compensation import (
    extract_compensation,
    format_compensation_display,
    meets_min_salary,
)


def _posting(
    *,
    title: str = "Software Engineer",
    company: str = "ACME",
    location: str = "Amsterdam, Netherlands",
    raw: dict | None = None,
) -> JobPosting:
    return JobPosting(
        external_id="1",
        title=title,
        company=company,
        location=location,
        url="https://acme.test/1",
        raw=raw or {},
    )


# --- format_compensation_display ------------------------------------------


def test_format_display_empty_when_no_info() -> None:
    posting = _posting(title="Engineer", location="Remote", raw={})
    assert format_compensation_display(posting) == ""


def test_format_display_min_only() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 100000,
                    }
                ]
            }
        }
    )
    assert format_compensation_display(posting) == "$100K+"


def test_format_display_max_only() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "EUR",
                        "maxValue": 80000,
                    }
                ]
            }
        }
    )
    assert format_compensation_display(posting) == "Up to €80K"


def test_format_display_equal_min_max_collapses() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "GBP",
                        "minValue": 150000,
                        "maxValue": 150000,
                    }
                ]
            }
        }
    )
    assert format_compensation_display(posting) == "£150K"


def test_format_display_range_from_structured_without_display() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 120000,
                        "maxValue": 180000,
                    }
                ]
            }
        }
    )
    assert format_compensation_display(posting) == "$120K to $180K"


def test_format_display_uses_iso_code_for_unmapped_currency() -> None:
    """CHF/SEK must not be mislabeled with a USD dollar sign."""
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "CHF",
                        "minValue": 120000,
                        "maxValue": 150000,
                    }
                ]
            }
        }
    )
    assert format_compensation_display(posting) == "CHF 120K to CHF 150K"


def test_format_display_omits_prefix_when_currency_unknown() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "minValue": 90000,
                    }
                ]
            }
        }
    )
    assert format_compensation_display(posting) == "90K+"


def test_format_display_normalizes_currency_code_case() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "eur",
                        "minValue": 80000,
                        "maxValue": 80000,
                    }
                ]
            }
        }
    )
    assert format_compensation_display(posting) == "€80K"


# --- ashby structured extraction edge cases -------------------------------


def test_ashby_hourly_interval_annualizes() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "HOUR",
                        "currencyCode": "USD",
                        "minValue": 50,
                        "maxValue": 60,
                    }
                ]
            }
        }
    )
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 50 * 2080
    assert info.max_annual == 60 * 2080


def test_ashby_monthly_interval_annualizes() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "MONTH",
                        "currencyCode": "USD",
                        "minValue": 8000,
                        "maxValue": 10000,
                    }
                ]
            }
        }
    )
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 96_000
    assert info.max_annual == 120_000
    assert meets_min_salary(posting, 80_000, "USD")
    assert not meets_min_salary(posting, 100_000, "USD")


def test_ashby_skips_components_without_values() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {"compensationType": "Salary", "interval": "1 YEAR", "currencyCode": "USD"},
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 100000,
                    },
                ]
            }
        }
    )
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 100000


def test_ashby_display_only_when_no_components() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "scrapeableCompensationSalarySummary": "Competitive package",
            }
        }
    )
    info = extract_compensation(posting)
    assert info is not None
    assert info.display == "Competitive package"
    assert info.min_annual is None


def test_ashby_display_parseable_text_is_used() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "compensationTierSummary": "$200k - $250k",
            }
        }
    )
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 200_000
    assert info.max_annual == 250_000


def test_ashby_empty_compensation_dict_returns_none() -> None:
    posting = _posting(raw={"compensation": {}})
    assert extract_compensation(posting) is None
