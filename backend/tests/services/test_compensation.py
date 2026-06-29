"""Tests for compensation extraction and salary filtering."""

from app.scrapers.types import JobPosting
from app.services.compensation import (
    extract_compensation,
    format_compensation_display,
    meets_min_salary,
)
from app.services.posting_filters import matches_posting_filters


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


def test_extract_compensation_from_ashby_summary_components() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "scrapeableCompensationSalarySummary": "$211.4K - $290.6K",
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 211400,
                        "maxValue": 290600,
                    }
                ],
            }
        }
    )

    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 211400
    assert info.max_annual == 290600
    assert info.currency == "USD"
    assert format_compensation_display(posting) == "$211.4K - $290.6K"


def test_extract_compensation_from_text_range() -> None:
    posting = _posting(title="Engineer", location="Remote", raw={})
    posting = _posting(title="Engineer ($120k - $150k)", location="Remote")

    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 120_000
    assert info.max_annual == 150_000
    assert info.currency == "USD"


def test_meets_min_salary_allows_unknown() -> None:
    posting = _posting()
    assert meets_min_salary(posting, 100_000)


def test_meets_min_salary_compares_when_known() -> None:
    high = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 180000,
                        "maxValue": 220000,
                    }
                ]
            }
        }
    )
    low = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 90000,
                        "maxValue": 110000,
                    }
                ]
            }
        }
    )

    assert meets_min_salary(high, 150_000, "USD")
    assert not meets_min_salary(low, 150_000, "USD")


def test_meets_min_salary_skips_currency_mismatch() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "EUR",
                        "minValue": 50000,
                        "maxValue": 60000,
                    }
                ]
            }
        }
    )
    assert meets_min_salary(posting, 200_000, "USD")


def test_min_salary_filter_in_posting_filters() -> None:
    rich = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 200000,
                        "maxValue": 250000,
                    }
                ]
            }
        }
    )
    modest = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 120000,
                        "maxValue": 150000,
                    }
                ]
            }
        }
    )
    filters = {"min_salary": 180000, "salary_currency": "USD"}

    assert matches_posting_filters(rich, filters)
    assert not matches_posting_filters(modest, filters)
