"""Tests for text-based compensation parsing and structural Ashby branches."""

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


# --- _from_text ------------------------------------------------------------


def test_from_text_eu_thousands_via_salary_field() -> None:
    posting = _posting(raw={"salary": "€55.000"})
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 55_000
    assert info.max_annual == 55_000
    assert info.currency == "EUR"


def test_from_text_single_amount_via_pay_field() -> None:
    posting = _posting(raw={"pay": "€75k"})
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 75_000
    assert info.max_annual == 75_000
    assert info.currency == "EUR"


def test_from_text_currency_code_word() -> None:
    posting = _posting(raw={"compensationSummary": "USD 130000"})
    info = extract_compensation(posting)
    assert info is not None
    assert info.currency == "USD"
    assert info.min_annual == 130_000


def test_millions_suffix_and_display_format() -> None:
    posting = _posting(title="Founder ($1.5M)", location="Remote")
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 1_500_000
    assert format_compensation_display(posting) == "Founder ($1.5M)"


# --- meets_min_salary edge -------------------------------------------------


def test_meets_min_salary_exact_boundary() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 100000,
                        "maxValue": 120000,
                    }
                ]
            }
        }
    )
    assert meets_min_salary(posting, 100_000, "USD") is True


# --- ashby structural branches --------------------------------------------


def test_ashby_salary_components_present_but_no_values_or_display() -> None:
    # salary_components exist but every value is None and there is no display,
    # so the structured branch yields nothing and _from_ashby returns None.
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {"compensationType": "Salary", "interval": "1 YEAR"},
                ]
            }
        }
    )
    assert extract_compensation(posting) is None


def test_ashby_no_salary_components_falls_through_to_display() -> None:
    # Components exist but none are Salary type -> salary_components empty,
    # so it falls to the display-only branch.
    posting = _posting(
        raw={
            "compensation": {
                "scrapeableCompensationSalarySummary": "Equity + benefits",
                "summaryComponents": [
                    {"compensationType": "Bonus", "interval": "1 YEAR", "minValue": 5000},
                ],
            }
        }
    )
    info = extract_compensation(posting)
    assert info is not None
    assert info.display == "Equity + benefits"


def test_ashby_currency_code_non_string_skipped() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": 123,
                        "minValue": 100000,
                    }
                ]
            }
        }
    )
    info = extract_compensation(posting)
    assert info is not None
    assert info.currency is None


def test_from_raw_first_text_field_unparseable_then_next() -> None:
    # "compensation" as a plain string is unparseable (no digits) -> loop
    # continues to "salary".
    posting = _posting(raw={"compensation": "see website", "salary": "$95k"})
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 95_000
