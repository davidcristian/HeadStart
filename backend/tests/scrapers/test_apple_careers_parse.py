import json
from typing import Any

import pytest

from app.scrapers.adapters.apple_careers_parse import (
    _format_location,
    _job_url,
    _posted_at,
    _to_posting,
    extract_hydration_data,
    parse_search_html,
)


def _hydration_html(data: Any) -> str:
    """Embed `data` the way Apple's search page does (JSON.parse of a JS string)."""
    escaped = json.dumps(data).replace("\\", "\\\\").replace('"', '\\"')
    return f'window.__staticRouterHydrationData = JSON.parse("{escaped}");'


def test_extract_missing_marker_raises() -> None:
    """No hydration marker in the HTML raises (line 23)."""
    with pytest.raises(ValueError, match="missing static router hydration data"):
        extract_hydration_data("<html>nothing here</html>")


def test_extract_invalid_json_raises() -> None:
    """A payload that is not valid JSON raises (lines 27-28)."""
    html = 'window.__staticRouterHydrationData = JSON.parse("{not json}");'
    with pytest.raises(ValueError, match="not valid JSON"):
        extract_hydration_data(html)


def test_extract_non_object_payload_raises() -> None:
    """A JSON array (not object) payload raises (line 30)."""
    with pytest.raises(ValueError, match="must be an object"):
        extract_hydration_data(_hydration_html([1, 2, 3]))


def test_parse_missing_loader_data_raises() -> None:
    """loaderData not a dict raises (line 44)."""
    with pytest.raises(ValueError, match="missing loaderData"):
        parse_search_html(_hydration_html({"loaderData": "x"}), company="Apple", locale="en-us")


def test_parse_missing_search_loader_raises() -> None:
    """search not a dict raises (line 47)."""
    html = _hydration_html({"loaderData": {"search": "x"}})
    with pytest.raises(ValueError, match="missing search loader"):
        parse_search_html(html, company="Apple", locale="en-us")


def test_parse_search_results_not_array_raises() -> None:
    """searchResults not a list raises (line 50)."""
    html = _hydration_html({"loaderData": {"search": {"searchResults": {}}}})
    with pytest.raises(ValueError, match="searchResults must be an array"):
        parse_search_html(html, company="Apple", locale="en-us")


def test_parse_total_fallback_and_skips_non_dict() -> None:
    """Non-numeric totalRecords falls back to len; non-dict rows are skipped."""
    data = {
        "loaderData": {
            "search": {
                "searchResults": [
                    {"reqId": "1", "postingTitle": "A", "transformedPostingTitle": "a"},
                    "skip-me",
                ],
                "totalRecords": "nan",
            }
        }
    }
    postings, total = parse_search_html(_hydration_html(data), company="Apple", locale="en-us")
    assert total == 2
    assert [p.external_id for p in postings] == ["1"]


@pytest.mark.parametrize("total_records", [float("inf"), float("nan"), float("-inf")])
def test_parse_nonfinite_total_records_fallback(total_records: float) -> None:
    """JSON Infinity/NaN totalRecords must not raise on int() (SCR-05)."""
    data = {
        "loaderData": {
            "search": {
                "searchResults": [
                    {"reqId": "1", "postingTitle": "A", "transformedPostingTitle": "a"},
                ],
                "totalRecords": total_records,
            }
        }
    }
    postings, total = parse_search_html(_hydration_html(data), company="Apple", locale="en-us")
    assert total == 1
    assert [p.external_id for p in postings] == ["1"]


def test_to_posting_requires_id() -> None:
    """A job with no usable id raises (line 62)."""
    with pytest.raises(ValueError, match="missing id"):
        _to_posting({"postingTitle": "no id"}, company="Apple", locale="en-us")


def test_format_location_empty_when_missing() -> None:
    """Missing/empty locations returns "" (line 81)."""
    assert _format_location({}) == ""
    assert _format_location({"locations": []}) == ""


def test_format_location_skips_non_dict_items() -> None:
    """Non-dict location items are ignored (line 85)."""
    assert _format_location({"locations": ["x", {"city": "Austin"}]}) == "Austin"


def test_format_location_city_and_state() -> None:
    """city + state renders "City, State" (line 91)."""
    loc = {"locations": [{"city": "Cupertino", "stateProvince": "CA"}]}
    assert _format_location(loc) == "Cupertino, CA"


def test_format_location_city_only() -> None:
    """city without state renders city (line 93)."""
    assert _format_location({"locations": [{"city": "Austin"}]}) == "Austin"


def test_format_location_name_only() -> None:
    """name-only entry renders name (line 95)."""
    assert _format_location({"locations": [{"name": "Remote"}]}) == "Remote"


def test_format_location_country_only() -> None:
    """country-only entry renders country (line 97)."""
    assert _format_location({"locations": [{"countryName": "Canada"}]}) == "Canada"


def test_format_location_empty_entry_then_next() -> None:
    """An entry with no usable fields is skipped and the loop continues (96->83)."""
    loc = {"locations": [{"stateProvince": "CA"}, {"city": "Austin"}]}
    assert _format_location(loc) == "Austin"


def test_job_url_with_team_code() -> None:
    """A job with req_id, slug and a team dict yields a ?team= URL (106->108, 110->112)."""
    job = {
        "reqId": "42",
        "transformedPostingTitle": "engineer",
        "team": {"teamCode": "SFW"},
    }
    assert (
        _job_url(job, locale="en-us") == "https://jobs.apple.com/en-us/details/42/engineer?team=SFW"
    )


def test_job_url_without_team_code() -> None:
    """req_id + slug but no team code omits the query (skip line 111)."""
    job = {"reqId": "42", "transformedPostingTitle": "engineer", "team": "not-a-dict"}
    assert _job_url(job, locale="en-us") == "https://jobs.apple.com/en-us/details/42/engineer"


def test_job_url_fallback_to_search() -> None:
    """Missing slug falls back to the search page (line 113)."""
    assert _job_url({"reqId": "42"}, locale="en-us") == "https://jobs.apple.com/en-us/search"


def test_posted_at_missing_returns_none() -> None:
    """No postDateInGMT returns None (line 119)."""
    assert _posted_at({}) is None


def test_posted_at_invalid_returns_none() -> None:
    """An unparseable timestamp returns None (lines 123-124)."""
    assert _posted_at({"postDateInGMT": "not-a-date"}) is None


def test_posted_at_naive_gets_utc() -> None:
    """A naive ISO timestamp is stamped UTC (line 126)."""
    result = _posted_at({"postDateInGMT": "2026-05-01T12:00:00"})
    assert result is not None
    assert result.tzinfo is not None
    assert result.isoformat() == "2026-05-01T12:00:00+00:00"


def test_posted_at_aware_converts_to_utc() -> None:
    """A tz-aware timestamp is converted to UTC (line 127)."""
    result = _posted_at({"postDateInGMT": "2026-05-01T12:00:00+02:00"})
    assert result is not None
    assert result.isoformat() == "2026-05-01T10:00:00+00:00"


def test_posted_at_zulu_suffix() -> None:
    """A Z suffix is normalized before parsing (line 120 path)."""
    result = _posted_at({"postDateInGMT": "2026-05-01T12:00:00Z"})
    assert result is not None
    assert result.isoformat() == "2026-05-01T12:00:00+00:00"
