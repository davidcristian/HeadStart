"""Unit tests for Google Careers job-detail parsing helpers."""

from __future__ import annotations

import pytest

from app.appliers.adapters.google_careers_detail import (
    parse_apply_link,
    parse_job_detail_page,
    resolve_external_id,
)

_APPLY_LINK = (
    "https://www.google.com/about/careers/applications/signin?"
    "jobId=TOKEN123&loc=AU&title=Software+Engineer"
)


def _ds0(record_json: str) -> str:
    return (
        "<html><script>AF_initDataCallback({key: 'ds:0', hash: '1', "
        f"data:{record_json}, sideChannel: {{}}}});</script></html>"
    )


def test_resolve_external_id_from_url_and_fallback() -> None:
    url = "https://www.google.com/about/careers/applications/jobs/results/12345-software-engineer"
    assert resolve_external_id(url, "fb") == "12345"
    assert resolve_external_id("no-results-here", "fallback-id") == "fallback-id"


def test_parse_apply_link_success() -> None:
    apply_job_id, loc, apply_url = parse_apply_link(_APPLY_LINK, title="Ignored")
    assert apply_job_id == "TOKEN123"
    assert loc == "AU"
    assert "title=Software+Engineer" in apply_url


def test_parse_apply_link_uses_title_fallback() -> None:
    link = "https://www.google.com/about/careers/applications/signin?jobId=T&loc=US"
    _, _, apply_url = parse_apply_link(link, title="Senior Dev, Backend")
    # Title falls back to the portion before the comma, spaces -> '+'.
    assert "title=Senior+Dev" in apply_url


def test_parse_apply_link_missing_job_id_raises() -> None:
    with pytest.raises(ValueError, match="missing apply jobId"):
        parse_apply_link(
            "https://www.google.com/about/careers/applications/signin?loc=US",
            title="Dev",
        )


def test_parse_job_detail_page_no_ds0_returns_none() -> None:
    assert parse_job_detail_page("<html>nothing</html>") is None


def test_parse_job_detail_page_no_data_key_returns_none() -> None:
    html = "<html><script>AF_initDataCallback({key: 'ds:0', hash: '1'});</script></html>"
    assert parse_job_detail_page(html) is None


def test_parse_job_detail_page_no_array_after_data_returns_none() -> None:
    html = (
        "<html><script>AF_initDataCallback({key: 'ds:0', data: \"not-an-array\"});</script></html>"
    )
    assert parse_job_detail_page(html) is None


def test_parse_job_detail_page_empty_payload_returns_none() -> None:
    assert parse_job_detail_page(_ds0("[]")) is None


def test_parse_job_detail_page_unbalanced_array_returns_none() -> None:
    # A '[' after data: but the brackets never close -> balanced parser returns None.
    html = "<html><script>AF_initDataCallback({key: 'ds:0', data: [[[unbalanced without closing"
    assert parse_job_detail_page(html) is None


def test_parse_job_detail_page_scalar_record_returns_none() -> None:
    # payload[0] is a scalar (not a list) -> record is not a list -> None.
    assert parse_job_detail_page(_ds0('["scalar"]')) is None


def test_parse_job_detail_page_short_record_returns_none() -> None:
    # record has < 6 entries.
    assert parse_job_detail_page(_ds0('[["1", "Title", "link"]]')) is None


def test_parse_job_detail_page_missing_fields_returns_none() -> None:
    # 6-length record but external_id blank -> _record_to_detail returns None.
    assert parse_job_detail_page(_ds0('[["", "Title", "link", 0, 0, ""]]')) is None


def test_parse_job_detail_page_full_record() -> None:
    record = (
        "[["
        '"55555",'
        '"Software Engineer",'
        f'"{_APPLY_LINK}",'
        "0,0,"
        '"companies/abc",'
        "0,"
        '"Alphabet",'
        "0,"
        '[["Sydney NSW, Australia"]]'
        "]]"
    )
    detail = parse_job_detail_page(_ds0(record))
    assert detail is not None
    assert detail.external_id == "55555"
    assert detail.company == "Alphabet"
    assert detail.company_resource == "companies/abc"
    assert detail.location_code == "AU"
    assert detail.location_label == "Sydney NSW, Australia"


def test_parse_job_detail_page_nested_record_unwrap() -> None:
    # payload[0] is a list whose first element is itself a list -> record = record[0].
    inner = f'["77777","Engineer","{_APPLY_LINK}",0,0,"",0,0]'
    record = f"[[{inner}]]"
    detail = parse_job_detail_page(_ds0(record))
    assert detail is not None
    assert detail.external_id == "77777"
    # record[7] falsy -> company defaults to Google; company_resource "" branch.
    assert detail.company == "Google"
    assert detail.company_resource == ""


def test_parse_job_detail_page_location_label_empty_variants() -> None:
    # record[9] present but not a well-formed nested list -> location_label "".
    record = f'[["88888","Engineer","{_APPLY_LINK}",0,0,"",0,"Google",0,[[]]]]'
    detail = parse_job_detail_page(_ds0(record))
    assert detail is not None
    assert detail.location_label == ""


def test_parse_job_detail_page_location_label_non_list_first() -> None:
    record = f'[["99999","Engineer","{_APPLY_LINK}",0,0,"",0,"Google",0,["scalar"]]]'
    detail = parse_job_detail_page(_ds0(record))
    assert detail is not None
    assert detail.location_label == ""
