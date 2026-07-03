"""Tests for the Apple Careers job-detail page parser."""

import json

import pytest

from app.appliers.adapters.apple_careers_detail import parse_job_detail_page


def _make_html(data: object) -> str:
    payload = json.dumps(json.dumps(data))[1:-1]
    return (
        f'<html><body>window.__staticRouterHydrationData = JSON.parse("{payload}");</body></html>'
    )


def test_parse_missing_loader_data() -> None:
    with pytest.raises(ValueError, match="missing loaderData"):
        parse_job_detail_page(_make_html({"loaderData": "not-a-dict"}))


def test_parse_missing_job_details() -> None:
    with pytest.raises(ValueError, match="missing jobDetails"):
        parse_job_detail_page(_make_html({"loaderData": {"jobDetails": "nope"}}))


def test_parse_missing_jobs_data() -> None:
    with pytest.raises(ValueError, match="missing jobsData"):
        parse_job_detail_page(_make_html({"loaderData": {"jobDetails": {"jobsData": []}}}))


def test_parse_missing_position_id() -> None:
    data = {"loaderData": {"jobDetails": {"jobsData": {"postingTitle": "t"}}}}
    with pytest.raises(ValueError, match="missing position id"):
        parse_job_detail_page(_make_html(data))


def test_parse_defaults_when_optional_fields_absent() -> None:
    data = {
        "loaderData": {
            "jobDetails": {
                "jobsData": {
                    "id": "REQ-1",
                    "locations": "not-a-list",
                }
            },
            "root": "not-a-dict",
        }
    }
    detail = parse_job_detail_page(_make_html(data))
    assert detail.position_id == "REQ-1"
    assert detail.job_number == "REQ-1"
    assert detail.locations == ()
    assert detail.locale == "en-us"
    assert detail.pipeline_type is None


def test_parse_root_locale_used_without_locale_info() -> None:
    data = {
        "loaderData": {
            "jobDetails": {"jobsData": {"id": "REQ-2", "localeInfo": "not-a-dict"}},
            "root": {"locale": "EN-GB"},
        }
    }
    detail = parse_job_detail_page(_make_html(data))
    assert detail.locale == "en-gb"
