"""Unit tests for LinkedIn apply common helpers (linkedin_common)."""

from __future__ import annotations

import pytest

from app.appliers.adapters.linkedin_common import (
    build_graphql_url,
    build_graphql_variables_string,
    decode_linkedin_redirect,
    extract_code_comment,
    has_linkedin_session_cookies,
    resolve_csrf_token,
    resolve_job_posting_url,
    voyager_request_cookies,
    voyager_request_headers,
)

# --- resolve_job_posting_url -------------------------------------------------


def test_resolve_job_posting_url_uses_numeric_id() -> None:
    url = resolve_job_posting_url("4434410881", "")
    assert url.endswith("/jobPosting/4434410881")


def test_resolve_job_posting_url_falls_back_to_view_url() -> None:
    url = resolve_job_posting_url(
        "",
        "https://www.linkedin.com/jobs/view/python-developer-at-cgi-4432008529",
    )
    assert url.endswith("/jobPosting/4432008529")


def test_resolve_job_posting_url_view_url_without_id_raises() -> None:
    with pytest.raises(ValueError, match="numeric job id"):
        resolve_job_posting_url(
            "",
            "https://www.linkedin.com/jobs/view/python-developer-at-cgi",
        )


def test_resolve_job_posting_url_non_linkedin_url_raises() -> None:
    with pytest.raises(ValueError, match="numeric job id"):
        resolve_job_posting_url("", "https://example.com/careers/some-role")


def test_resolve_job_posting_url_empty_inputs_raise() -> None:
    with pytest.raises(ValueError):
        resolve_job_posting_url("", "")


# --- extract_code_comment ----------------------------------------------------


def test_extract_code_comment_reads_value() -> None:
    html = '<code id="referenceId"><!--"abc123=="--></code>'
    assert extract_code_comment(html, "referenceId") == "abc123=="


def test_extract_code_comment_missing_marker() -> None:
    assert extract_code_comment("<div></div>", "referenceId") is None


def test_extract_code_comment_no_comment_after_marker() -> None:
    html = '<code id="referenceId">no comment here</code>'
    assert extract_code_comment(html, "referenceId") is None


def test_extract_code_comment_unterminated_comment() -> None:
    html = '<code id="referenceId"><!--dangling'
    assert extract_code_comment(html, "referenceId") is None


def test_extract_code_comment_empty_value_returns_none() -> None:
    html = '<code id="referenceId"><!--  --></code>'
    assert extract_code_comment(html, "referenceId") is None


def test_extract_code_comment_non_matching_regex() -> None:
    # Comment present but regex cannot pull a value (empty between markers)
    html = '<code id="referenceId"><!----></code>'
    assert extract_code_comment(html, "referenceId") is None


# --- decode_linkedin_redirect ------------------------------------------------


def test_decode_linkedin_redirect_empty_string() -> None:
    assert decode_linkedin_redirect("   ") == ""


def test_decode_linkedin_redirect_unwraps_target() -> None:
    wrapped = (
        "https://www.linkedin.com/redir/redirect?url="
        "https%3A%2F%2Fboards.greenhouse.io%2Facme%2Fjobs%2F1"
    )
    assert decode_linkedin_redirect(wrapped) == "https://boards.greenhouse.io/acme/jobs/1"


def test_decode_linkedin_redirect_no_url_param_returns_input() -> None:
    wrapped = "https://www.linkedin.com/redir/redirect?other=1"
    assert decode_linkedin_redirect(wrapped) == wrapped


def test_decode_linkedin_redirect_plain_url_passthrough() -> None:
    plain = "https://example.com/apply"
    assert decode_linkedin_redirect(plain) == plain


# --- session cookie / csrf helpers -------------------------------------------


def test_has_linkedin_session_cookies_variants() -> None:
    assert has_linkedin_session_cookies(None) is False
    assert has_linkedin_session_cookies({"cookies": {}}) is False
    assert has_linkedin_session_cookies({"cookies": {"li_at": "x"}}) is False
    assert has_linkedin_session_cookies({"cookies": {"li_at": "x", "JSESSIONID": "y"}}) is True


def test_resolve_csrf_token_from_session() -> None:
    creds = {"session": {"csrf_token": "ajax:token"}, "cookies": {}}
    assert resolve_csrf_token(creds) == "ajax:token"


def test_resolve_csrf_token_blank_session_value_falls_through() -> None:
    creds = {"session": {"csrf_token": "   "}, "cookies": {"JSESSIONID": '"raw-id"'}}
    assert resolve_csrf_token(creds) == "ajax:raw-id"


def test_resolve_csrf_token_from_jsessionid_already_ajax() -> None:
    creds = {"session": {}, "cookies": {"JSESSIONID": "ajax:existing"}}
    assert resolve_csrf_token(creds) == "ajax:existing"


def test_resolve_csrf_token_none_when_absent() -> None:
    assert resolve_csrf_token(None) is None
    assert resolve_csrf_token({"session": {}, "cookies": {}}) is None


# --- voyager headers / cookies -----------------------------------------------


def test_voyager_request_headers_without_credentials() -> None:
    headers = voyager_request_headers(None)
    assert "csrf-token" not in headers
    assert headers["x-restli-protocol-version"] == "2.0.0"


def test_voyager_request_headers_with_csrf_and_extra() -> None:
    creds = {
        "session": {"csrf_token": "ajax:t"},
        "cookies": {},
        "headers": {"X-Custom": "1"},
    }
    headers = voyager_request_headers(creds)
    assert headers["csrf-token"] == "ajax:t"
    assert headers["X-Custom"] == "1"
    assert headers["x-li-graphql-pegasus-client"] == "true"


def test_voyager_request_cookies() -> None:
    assert voyager_request_cookies(None) == {}
    assert voyager_request_cookies({"cookies": {"li_at": "x"}}) == {"li_at": "x"}


# --- graphql serialization ---------------------------------------------------


def test_build_graphql_variables_string_all_types() -> None:
    encoded = build_graphql_variables_string(
        {
            "flag": True,
            "off": False,
            "num": 5,
            "items": ["a b", 2],
        }
    )
    assert "flag:true" in encoded
    assert "off:false" in encoded
    assert "num:5" in encoded
    assert "List(a%20b,2)" in encoded


def test_build_graphql_url_with_query_name() -> None:
    url = build_graphql_url(
        query_id="qid",
        variables={"jobPostingUrn": "urn:1"},
        query_name="MyQuery",
    )
    assert "queryId=qid" in url
    assert "queryName=MyQuery" in url


def test_build_graphql_url_without_query_name() -> None:
    url = build_graphql_url(query_id="qid", variables={})
    assert "queryName" not in url
