"""Tests for Indeed viewjob page parsing helpers."""

from __future__ import annotations

import pytest

from app.appliers.adapters.indeed_detail import (
    _company_name,
    _external_apply_url,
    _initial_to_detail,
    _job_field,
    extract_initial_data,
    parse_viewjob_page,
    resolve_viewjob_url,
)


def _host_query(job: dict) -> dict:
    return {
        "hostQueryExecutionResult": {"data": {"jobData": {"results": [{"job": job}]}}},
    }


def test_extract_initial_data_no_marker() -> None:
    assert extract_initial_data("<html>no data</html>") is None


def test_extract_initial_data_no_opening_brace() -> None:
    assert extract_initial_data("window._initialData = ") is None


def test_extract_initial_data_unbalanced_json() -> None:
    assert extract_initial_data("window._initialData = {unbalanced") is None


def test_extract_initial_data_invalid_json() -> None:
    assert extract_initial_data("window._initialData = {not: valid}") is None


def test_extract_initial_data_non_dict_json() -> None:
    assert extract_initial_data("window._initialData = [1, 2, 3]") is None


def test_extract_initial_data_valid() -> None:
    assert extract_initial_data('window._initialData = {"jobKey": "k"}') == {"jobKey": "k"}


def test_parse_viewjob_page_returns_none_without_initial_data() -> None:
    assert parse_viewjob_page("<html></html>") is None


def test_resolve_viewjob_url_prefers_existing_viewjob_url() -> None:
    assert resolve_viewjob_url("k", "https://www.indeed.com/viewjob?jk=k", {}) == (
        "https://www.indeed.com/viewjob?jk=k"
    )


def test_resolve_viewjob_url_with_http_host() -> None:
    assert resolve_viewjob_url("k", "", {"host": "https://uk.indeed.com/"}) == (
        "https://uk.indeed.com/viewjob?jk=k"
    )


def test_resolve_viewjob_url_default_host() -> None:
    assert resolve_viewjob_url("k", "", {}) == "https://www.indeed.com/viewjob?jk=k"


def test_initial_to_detail_uses_apply_attrs_job_key_and_continue_url() -> None:
    initial = {
        "jobTitle": "Engineer",
        "indeedApplyButtonContainer": {
            "indeedApplyButtonAttributes": {
                "indeedApplyableJobId": "applyable-1",
                "continueUrl": "https://smartapply.indeed.com/continue",
                "jk": "attr-key",
            }
        },
    }
    detail = _initial_to_detail(initial, fallback_job_key="")
    assert detail is not None
    assert detail.job_key == "attr-key"
    assert detail.indeed_applyable_job_id == "applyable-1"
    assert detail.apply_continue_url == "https://smartapply.indeed.com/continue"
    assert detail.easily_apply is True


def test_initial_to_detail_falls_back_to_host_query_key_and_title() -> None:
    initial = _host_query({"key": "hq-key", "title": "HQ Title", "expired": True})
    detail = _initial_to_detail(initial, fallback_job_key="")
    assert detail is not None
    assert detail.job_key == "hq-key"
    assert detail.title == "HQ Title"
    assert detail.expired is True
    assert detail.easily_apply is False


def test_initial_to_detail_returns_none_without_key_or_title() -> None:
    assert _initial_to_detail({"jobTitle": "Only Title"}, fallback_job_key="") is None
    assert _initial_to_detail({"jobKey": "only-key"}, fallback_job_key="") is None


def test_company_name_from_header_model() -> None:
    initial = {
        "jobInfoWrapperModel": {"jobInfoModel": {"jobInfoHeaderModel": {"companyName": "  ACME  "}}}
    }
    assert _company_name(initial) == "ACME"


def test_company_name_falls_back_to_source_employer() -> None:
    initial = _host_query({"sourceEmployerName": "Fallback Co"})
    assert _company_name(initial) == "Fallback Co"


def test_company_name_empty_header_falls_back() -> None:
    initial = {
        "jobInfoWrapperModel": {"jobInfoModel": {"jobInfoHeaderModel": {"companyName": "  "}}}
    }
    assert _company_name(initial) == ""


def test_company_name_non_dict_inner_models_fall_back() -> None:
    assert _company_name({"jobInfoWrapperModel": {"jobInfoModel": "nope"}}) == ""
    assert (
        _company_name({"jobInfoWrapperModel": {"jobInfoModel": {"jobInfoHeaderModel": "nope"}}})
        == ""
    )
    assert (
        _company_name(
            {"jobInfoWrapperModel": {"jobInfoModel": {"jobInfoHeaderModel": {"companyName": 123}}}}
        )
        == ""
    )


def test_external_apply_url_variants() -> None:
    assert _external_apply_url(_host_query({"url": "https://boards.greenhouse.io/x"})) == (
        "https://boards.greenhouse.io/x"
    )
    assert _external_apply_url(_host_query({"url": "  "})) is None
    assert _external_apply_url(_host_query({"url": "https://www.indeed.com/rc"})) is None
    assert _external_apply_url(_host_query({"url": 123})) is None


def test_job_field_guards() -> None:
    assert _job_field({"hostQueryExecutionResult": "nope"}, "x") is None
    assert _job_field({"hostQueryExecutionResult": {"data": "nope"}}, "x") is None
    assert _job_field({"hostQueryExecutionResult": {"data": {"jobData": "nope"}}}, "x") is None
    assert (
        _job_field({"hostQueryExecutionResult": {"data": {"jobData": {"results": []}}}}, "x")
        is None
    )
    assert (
        _job_field({"hostQueryExecutionResult": {"data": {"jobData": {"results": ["bad"]}}}}, "x")
        is None
    )
    assert (
        _job_field(
            {"hostQueryExecutionResult": {"data": {"jobData": {"results": [{"job": "bad"}]}}}}, "x"
        )
        is None
    )
    assert _job_field(_host_query({"x": "value"}), "x") == "value"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://indeed.com/x", None),
        ("https://www.indeed.com/x", None),
    ],
)
def test_external_apply_url_rejects_indeed_hosts(url: str, expected: object) -> None:
    assert _external_apply_url(_host_query({"url": url})) == expected
