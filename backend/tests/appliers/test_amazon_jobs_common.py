"""Tests for Amazon Jobs shared HTTP helpers."""

from app.appliers.adapters.amazon_jobs_common import (
    api_error_message,
    applicant_show_url,
    extract_application_id,
    has_session_cookies,
    job_details_url,
    request_headers,
    resolve_job_id,
)


def test_resolve_job_id_falls_back_to_external_id() -> None:
    # No config id and no /jobs/<id> URL match, so the external id is used.
    assert resolve_job_id({}, "https://example.com/careers", "  12345 ") == "12345"


def test_applicant_show_and_job_details_urls() -> None:
    assert applicant_show_url() == "https://www.amazon.jobs/api/apply/applicant"
    assert job_details_url("77").endswith("/api/apply/jobs/77/details")


def test_request_headers_without_json_body_and_without_credentials() -> None:
    headers = request_headers(referer="https://ref", json_body=False)
    assert "Content-Type" not in headers
    assert headers["Referer"] == "https://ref"


def test_request_headers_with_credentials_but_no_cookies() -> None:
    headers = request_headers(
        referer="https://ref",
        credentials={"headers": {"X-Custom": "1"}, "cookies": {}},
    )
    assert headers["X-Custom"] == "1"
    assert "Cookie" not in headers


def test_request_headers_includes_cookie_header() -> None:
    headers = request_headers(
        referer="https://ref",
        credentials={"cookies": {"session": "abc", "csrf": "xyz"}},
    )
    assert headers["Cookie"] == "session=abc; csrf=xyz"


def test_has_session_cookies_variants() -> None:
    assert has_session_cookies(None) is False
    assert has_session_cookies({"cookies": {}}) is False
    assert has_session_cookies({"cookies": {"session": "x"}}) is True
    assert has_session_cookies({"cookies": {"a": "1", "b": "2"}}) is True
    assert has_session_cookies({"cookies": {"only_one": "1"}}) is False


def test_api_error_message_variants() -> None:
    assert api_error_message("not a dict") is None
    assert api_error_message({"errors": "nope"}) is None
    assert api_error_message({"errors": []}) is None
    assert api_error_message({"errors": [{"message": "bad"}]}) == "bad"
    assert api_error_message({"errors": [{"error": "worse"}]}) == "worse"
    assert api_error_message({"errors": ["string"]}) == "amazon_jobs apply request failed"
    assert api_error_message({"errors": [{}]}) == "amazon_jobs apply request failed"


def test_extract_application_id_variants() -> None:
    assert extract_application_id("not a dict") is None
    assert extract_application_id({}) is None
    assert extract_application_id({"data": {"application_id": "d-1"}}) == "d-1"
    assert extract_application_id({"data": {}}) is None
    assert extract_application_id({"application": {"application_id": "a-1"}}) == "a-1"
    assert extract_application_id({"application": {}}) is None
