import pytest

from app.scrapers.adapters.uber_careers_parse import (
    coerce_int64,
    format_location,
    parse_search_response,
)

_BASE_URL = "https://www.uber.com/us/en/careers/list"


def test_parse_search_response_missing_data_field() -> None:
    postings, total = parse_search_response({}, company="Uber", careers_base_url=_BASE_URL)
    assert postings == []
    assert total is None


def test_parse_search_response_results_not_list() -> None:
    payload = {"data": {"totalResults": 5, "results": "nope"}}
    postings, total = parse_search_response(payload, company="Uber", careers_base_url=_BASE_URL)
    assert postings == []
    assert total == 5


def test_parse_search_response_skips_non_dict_items() -> None:
    payload = {
        "data": {
            "totalResults": 1,
            "results": ["not-a-dict", {"id": 42, "title": "Dev"}],
        }
    }
    postings, total = parse_search_response(payload, company="Uber", careers_base_url=_BASE_URL)
    assert total == 1
    assert len(postings) == 1
    assert postings[0].external_id == "42"
    assert postings[0].url == "https://www.uber.com/us/en/careers/list/42"


def test_coerce_int64_bool_returns_none() -> None:
    assert coerce_int64(True) is None


def test_coerce_int64_plain_int() -> None:
    assert coerce_int64(7) == 7


def test_coerce_int64_dict_low_and_high_none() -> None:
    assert coerce_int64({"low": None, "high": None}) is None


def test_coerce_int64_dict_high_shift() -> None:
    assert coerce_int64({"low": 0, "high": 1}) == (1 << 32)


def test_coerce_int64_unsupported_type_returns_none() -> None:
    assert coerce_int64("nope") is None


def test_format_location_none() -> None:
    assert format_location(None) == ""


def test_format_location_string_collapses_whitespace() -> None:
    assert format_location("  San  Francisco  ") == "San Francisco"


def test_format_location_list_dedupes_and_skips_empty() -> None:
    result = format_location(
        [
            {"city": "SF", "region": "CA", "countryName": "US"},
            "",
            {"city": "SF", "region": "CA", "countryName": "US"},
            {"city": "NYC", "region": "NY", "countryName": "US"},
        ]
    )
    assert result == "SF, CA, US; NYC, NY, US"


def test_format_location_dict_prefers_country_name_over_country() -> None:
    assert format_location({"city": "SF", "country": "USA", "countryName": "United States"}) == (
        "SF, United States"
    )


def test_format_location_dict_falls_back_to_country_code() -> None:
    assert format_location({"city": "SF", "country": "USA"}) == "SF, USA"


def test_format_location_dict_no_components_returns_empty() -> None:
    assert format_location({"city": "", "region": "", "country": ""}) == ""


def test_format_location_unsupported_type_returns_empty() -> None:
    assert format_location(123) == ""


def test_to_posting_missing_id_raises() -> None:
    payload = {"data": {"results": [{"title": "No id"}]}}
    with pytest.raises(ValueError, match="missing id"):
        parse_search_response(payload, company="Uber", careers_base_url=_BASE_URL)


def test_to_posting_uses_primary_location_without_fallback() -> None:
    payload = {
        "data": {
            "results": [
                {
                    "id": 1,
                    "title": "Dev",
                    "location": {"city": "Paris", "country": "FR"},
                    "allLocations": [{"city": "Berlin", "country": "DE"}],
                }
            ]
        }
    }
    postings, _ = parse_search_response(payload, company="Uber", careers_base_url=_BASE_URL)
    assert postings[0].location == "Paris, FR"


def test_to_posting_location_falls_back_to_all_locations() -> None:
    payload = {
        "data": {
            "results": [
                {
                    "id": 1,
                    "title": "Dev",
                    "location": None,
                    "allLocations": [{"city": "Berlin", "region": "BE", "country": "DE"}],
                }
            ]
        }
    }
    postings, _ = parse_search_response(payload, company="Uber", careers_base_url=_BASE_URL)
    assert postings[0].location == "Berlin, BE, DE"


def test_posted_at_skips_blank_and_uses_updated_date() -> None:
    payload = {
        "data": {
            "results": [
                {"id": 1, "title": "Dev", "creationDate": "", "updatedDate": "2026-01-02T03:00:00Z"}
            ]
        }
    }
    postings, _ = parse_search_response(payload, company="Uber", careers_base_url=_BASE_URL)
    assert postings[0].posted_at is not None
    assert postings[0].posted_at.year == 2026


def test_posted_at_invalid_iso_continues_then_none() -> None:
    payload = {"data": {"results": [{"id": 1, "title": "Dev", "creationDate": "not-a-date"}]}}
    postings, _ = parse_search_response(payload, company="Uber", careers_base_url=_BASE_URL)
    assert postings[0].posted_at is None


def test_posted_at_naive_datetime_gets_utc() -> None:
    payload = {
        "data": {"results": [{"id": 1, "title": "Dev", "creationDate": "2026-01-02T03:00:00"}]}
    }
    postings, _ = parse_search_response(payload, company="Uber", careers_base_url=_BASE_URL)
    posted = postings[0].posted_at
    assert posted is not None
    assert posted.tzinfo is not None


def test_posted_at_no_dates_returns_none() -> None:
    payload = {"data": {"results": [{"id": 1, "title": "Dev"}]}}
    postings, _ = parse_search_response(payload, company="Uber", careers_base_url=_BASE_URL)
    assert postings[0].posted_at is None
