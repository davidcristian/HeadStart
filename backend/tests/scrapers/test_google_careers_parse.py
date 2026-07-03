import json
from typing import Any

from app.scrapers.adapters.google_careers_parse import (
    _balanced_json_value,
    _extract_job_records,
    _job_url,
    _location_from_record,
    _posted_at_from_record,
    _slugify,
    _to_posting,
    parse_search_page,
)

_BASE = "https://www.google.com/about/careers/applications"


def _page(records: list[list[Any]]) -> str:
    """Wrap records in the AF_initDataCallback envelope Google uses."""
    blob = json.dumps([records])
    return f"prefix AF_initDataCallback({{key: 'ds:1', hash: '1', data:{blob}}}); suffix"


def _record(external_id: str, title: str, **_: Any) -> list[Any]:
    return [external_id, title]


def test_parse_search_page_skips_none_records() -> None:
    """A record that maps to None is skipped and the loop continues (37->29)."""
    records = [["", "no id"], ["1", "Real Job"]]
    postings = parse_search_page(
        _page(records), company="Google", applications_base=_BASE, query_params={}
    )
    assert [p.external_id for p in postings] == ["1"]


def test_extract_no_marker_returns_empty() -> None:
    """No init-data marker yields no records (line 45)."""
    assert _extract_job_records("<html>nothing</html>") == []


def test_extract_no_data_key_returns_empty() -> None:
    """Marker present but no data: key yields no records (line 48)."""
    html = "AF_initDataCallback({key: 'ds:1', hash: '1'});"
    assert _extract_job_records(html) == []


def test_extract_no_opening_bracket_returns_empty() -> None:
    """data: with no following list bracket yields no records (line 51)."""
    html = "AF_initDataCallback({key: 'ds:1', data: null });"
    assert _extract_job_records(html) == []


def test_extract_unbalanced_blob_returns_empty() -> None:
    """An unbalanced JSON blob yields no records (line 54)."""
    html = "AF_initDataCallback({key: 'ds:1', data:[[1, 2"
    assert _extract_job_records(html) == []


def test_extract_invalid_json_returns_empty() -> None:
    """A balanced-but-invalid JSON blob yields no records (line 60)."""
    html = "AF_initDataCallback({key: 'ds:1', data:[abc]});"
    assert _extract_job_records(html) == []


def test_extract_empty_payload_returns_empty() -> None:
    """An empty top-level list yields no records (line 63)."""
    html = "AF_initDataCallback({key: 'ds:1', data:[]});"
    assert _extract_job_records(html) == []


def test_extract_payload_first_not_list_returns_empty() -> None:
    """payload[0] not being a list yields no records (line 70)."""
    html = "AF_initDataCallback({key: 'ds:1', data:[\"nope\"]});"
    assert _extract_job_records(html) == []


def test_extract_filters_non_list_jobs() -> None:
    """Non-list/empty job entries inside the jobs list are filtered out."""
    html = _page([["1", "Job A"], [], "skip"])  # type: ignore[list-item]
    records = _extract_job_records(html)
    assert records == [["1", "Job A"]]


def test_balanced_value_rejects_non_bracket_opener() -> None:
    """A start position not on [ or { returns None (line 79)."""
    assert _balanced_json_value("abc", 0) is None


def test_balanced_value_handles_escaped_string() -> None:
    """A quoted string with escapes is walked correctly (line 81 escape branch)."""
    text = '["a\\"b]", "c"]'
    assert _balanced_json_value(text, 0) == text


def test_balanced_value_unterminated_returns_none() -> None:
    """A never-closing structure returns None (line 94)."""
    assert _balanced_json_value("[1, 2, 3", 0) is None


def test_to_posting_too_short_returns_none() -> None:
    """A record with fewer than 2 fields returns None (line 106)."""
    assert (
        _to_posting(
            ["only"], company="Google", applications_base=_BASE, query_params={}, slug_by_id={}
        )
        is None
    )


def test_to_posting_missing_id_or_title_returns_none() -> None:
    """Missing id or title returns None (line 110)."""
    assert (
        _to_posting(
            ["", "title"], company="Google", applications_base=_BASE, query_params={}, slug_by_id={}
        )
        is None
    )
    assert (
        _to_posting(
            ["1", ""], company="Google", applications_base=_BASE, query_params={}, slug_by_id={}
        )
        is None
    )


def test_to_posting_default_company_when_field_absent() -> None:
    """A short record keeps the default company (113->116 not-taken)."""
    posting = _to_posting(
        ["1", "Job"], company="Google", applications_base=_BASE, query_params={}, slug_by_id={}
    )
    assert posting is not None
    assert posting.company == "Google"


def test_to_posting_company_override_from_record() -> None:
    """record[7] overrides the company when present (line 114)."""
    record: list[Any] = ["1", "Job", None, None, None, None, None, "Waymo"]
    posting = _to_posting(
        record, company="Google", applications_base=_BASE, query_params={}, slug_by_id={}
    )
    assert posting is not None
    assert posting.company == "Waymo"


def test_location_from_record_too_short_returns_empty() -> None:
    """A record without index 9 returns "" (line 138)."""
    assert _location_from_record(["1", "Job"]) == ""


def test_location_from_record_bad_shape_returns_empty() -> None:
    """A malformed location list returns "" (line 142)."""
    record: list[Any] = ["1", "Job"] + [None] * 7 + [[["", "x"]]]
    # record[9][0] is a list but first[0] is empty -> falsy -> falls through
    record[9] = ["not-a-list"]
    assert _location_from_record(record) == ""


def test_location_from_record_extracts_first() -> None:
    """A well-formed location list returns the first name."""
    record: list[Any] = ["1", "Job"] + [None] * 7 + [[["Dublin, Ireland"]]]
    assert _location_from_record(record) == "Dublin, Ireland"


def test_posted_at_too_short_returns_none() -> None:
    """A record without index 12 returns None (line 147)."""
    assert _posted_at_from_record(["1", "Job"]) is None


def test_posted_at_non_numeric_returns_none() -> None:
    """A non-numeric timestamp returns None (line 150)."""
    record: list[Any] = ["1", "Job"] + [None] * 10 + [["not-a-number"]]
    assert _posted_at_from_record(record) is None


def test_posted_at_valid() -> None:
    """A numeric epoch is parsed to a UTC datetime."""
    record: list[Any] = ["1", "Job"] + [None] * 10 + [[1766750430]]
    result = _posted_at_from_record(record)
    assert result is not None
    assert result.tzinfo is not None


def test_slugify_falls_back_to_job() -> None:
    """A title with no alphanumerics slugifies to "job" (lines 155-156)."""
    assert _slugify("!!!") == "job"


def test_slugify_normal() -> None:
    assert _slugify("Software Engineer II") == "software-engineer-ii"


def test_job_url_with_query_params() -> None:
    """query_params are appended to the job URL (line 169)."""
    url = _job_url(applications_base=_BASE, external_id="1", slug="job", query_params={"q": "swe"})
    assert url == f"{_BASE}/jobs/results/1-job?q=swe"


def test_job_url_without_query_params() -> None:
    url = _job_url(applications_base=_BASE, external_id="1", slug="job", query_params={})
    assert url == f"{_BASE}/jobs/results/1-job"
