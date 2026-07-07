"""Tests for the Apple Careers shared apply helpers."""

from app.appliers.adapters.apple_careers_common import (
    apply_error_message,
    csrf_token_url,
    extract_application_id,
    has_session_cookies,
    parse_details_path,
    request_headers,
    resolve_csrf_token,
    resolve_job_detail_url,
    resolve_talent_id,
    unwrap_response,
)


def test_resolve_job_detail_url_uses_configured_detail_url() -> None:
    assert (
        resolve_job_detail_url({"job_detail_url": "https://jobs.apple.com/x  "}, "  ", "id")
        == "https://jobs.apple.com/x"
    )
    assert (
        resolve_job_detail_url({"detail_url": "https://jobs.apple.com/y"}, "", "id")
        == "https://jobs.apple.com/y"
    )


def test_resolve_job_detail_url_builds_from_slug_and_team() -> None:
    url = resolve_job_detail_url(
        {"slug": "ai-engineer", "req_id": "REQ-1", "team": "SFTWR", "locale": "en-gb"},
        "",
        "fallback",
    )
    assert url == "https://jobs.apple.com/en-gb/details/REQ-1/ai-engineer?team=SFTWR"


def test_resolve_job_detail_url_builds_slug_without_team() -> None:
    url = resolve_job_detail_url({"transformed_posting_title": "ai-engineer"}, "", "REQ-2")
    assert url == "https://jobs.apple.com/en-us/details/REQ-2/ai-engineer"


def test_resolve_job_detail_url_without_slug_uses_req_id_only() -> None:
    url = resolve_job_detail_url({"position_id": "REQ-3"}, "", "")
    assert url == "https://jobs.apple.com/en-us/details/REQ-3"


def test_resolve_job_detail_url_returns_none_without_req_id() -> None:
    assert resolve_job_detail_url({}, "", "") is None


def test_csrf_token_url() -> None:
    assert csrf_token_url() == "https://jobs.apple.com/api/v1/js/CSRFToken"


def test_resolve_talent_id_reads_alternate_session_keys() -> None:
    creds = {"session": {"talentID": "tid-9"}}
    assert resolve_talent_id(creds, {}) == "tid-9"


def test_resolve_talent_id_falls_back_to_config_when_session_missing() -> None:
    creds = {"session": {"unrelated": "x"}}
    assert resolve_talent_id(creds, {"talentId": "cfg-7"}) == "cfg-7"


def test_resolve_csrf_token_reads_headers_then_config() -> None:
    assert resolve_csrf_token(None, {"csrf": "cfg-csrf"}) == "cfg-csrf"
    creds_headers = {"session": {}, "headers": {"X-Apple-CSRF-Token": "hdr-csrf"}}
    assert resolve_csrf_token(creds_headers, {}) == "hdr-csrf"
    creds_alt = {"session": {"apple_csrf_token": "alt-csrf"}}
    assert resolve_csrf_token(creds_alt, {}) == "alt-csrf"


def test_resolve_csrf_token_returns_none_when_absent() -> None:
    assert resolve_csrf_token({"session": {}, "headers": {}}, {}) is None


def test_has_session_cookies_variants() -> None:
    assert has_session_cookies(None) is False
    assert has_session_cookies({"cookies": {}}) is False
    assert has_session_cookies({"cookies": {"foo": "1", "bar": "2"}}) is True
    assert has_session_cookies({"cookies": {"only": "1"}}) is False


def test_request_headers_without_credentials_omits_cookie() -> None:
    headers = request_headers(csrf_token="c", referer="https://jobs.apple.com/app")
    assert "Cookie" not in headers
    assert headers["Content-Type"] == "application/json"


def test_request_headers_with_empty_cookies_skips_cookie_header() -> None:
    headers = request_headers(
        csrf_token="c",
        referer="https://jobs.apple.com/app",
        credentials={"headers": {}, "cookies": {}},
        json_body=False,
    )
    assert "Cookie" not in headers
    assert "Content-Type" not in headers


def test_unwrap_response_data_only_and_passthrough() -> None:
    assert unwrap_response({"data": {"a": 1}}) == {"a": 1}
    assert unwrap_response(["not", "a", "dict"]) == ["not", "a", "dict"]


def test_apply_error_message_variants() -> None:
    assert apply_error_message("not a dict") is None
    assert apply_error_message({"success": True}) is None
    assert apply_error_message({"success": False, "errors": [{"message": "bad"}]}) == "bad"
    assert apply_error_message({"success": False, "errors": [{"error": "worse"}]}) == "worse"
    failed = "apple_careers apply request failed"
    assert apply_error_message({"success": False, "errors": [{}]}) == failed
    assert apply_error_message({"success": False, "errors": ["x"]}) == failed
    assert apply_error_message({"success": False, "message": "closed req"}) == "closed req"
    assert apply_error_message({"success": False, "error": "plain error"}) == "plain error"
    assert apply_error_message({"success": False}) == "apple_careers apply request failed"
    # APL-28: bare errors/error envelopes without success:false
    assert apply_error_message({"errors": [{"message": "missing required answer"}]}) == (
        "missing required answer"
    )
    assert apply_error_message({"errors": [{"error": "worse"}]}) == "worse"
    assert apply_error_message({"errors": [{}]}) is None
    assert apply_error_message({"errors": ["string"]}) is None
    assert apply_error_message({"error": {"message": "validation failed"}}) == "validation failed"
    assert apply_error_message({"error": {"message": ""}}) is None
    assert apply_error_message({"error": "plain error"}) == "plain error"
    assert apply_error_message({"error": "  "}) is None
    assert apply_error_message({"status": 200}) is None


def test_extract_application_id_non_dict_and_roles_lookup() -> None:
    assert extract_application_id("not a dict") is None
    assert extract_application_id({"success": True, "data": {"roles": {"id": "r-1"}}}) == "r-1"
    # roles present as a dict but no matching id -> loop exhausts, returns None
    none_roles = {"success": True, "data": {"roles": {"applicationId": None}}}
    assert extract_application_id(none_roles) is None
    # roles absent / not a dict -> isinstance guard is False, returns None
    assert extract_application_id({"success": True, "data": {"roles": "nope"}}) is None


def test_parse_details_path_returns_none_without_match() -> None:
    assert parse_details_path("https://example.com/no-details-here") is None
