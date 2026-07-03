"""Unit tests for Meta Careers apply helper modules (common, detail, payload)."""

from __future__ import annotations

import pytest

from app.appliers.adapters.meta_careers_common import (
    extract_application_id,
    has_session_cookies,
    request_headers,
    resolve_requisition_id,
    resolve_session_id,
)
from app.appliers.adapters.meta_careers_detail import (
    MetaCareersJobDetail,
    _html_blob,
    _item_list,
    _string_list,
    parse_job_detail_response,
)
from app.appliers.adapters.meta_careers_payload import (
    _cover_letter_text,
    _drop_empty,
    _yes_no_answer,
    build_application_state,
)
from app.schemas.profile import ProfileData

JOB_ID = "2132019417725760"


def _detail() -> MetaCareersJobDetail:
    return MetaCareersJobDetail(
        requisition_id=JOB_ID,
        title="TPM",
        locations=("Menlo Park, CA",),
        departments=(),
        description_html="",
        minimum_qualifications=(),
        preferred_qualifications=(),
        responsibilities=(),
    )


def _profile(**overrides: object) -> ProfileData:
    base: dict[str, object] = {"full_name": "Ada Lovelace", "email": "ada@example.com"}
    base.update(overrides)
    return ProfileData(**base)


# --- resolve_requisition_id --------------------------------------------------


def test_resolve_requisition_id_from_url() -> None:
    url = f"https://www.metacareers.com/jobs/{JOB_ID}/"
    assert resolve_requisition_id({}, url, "ignored") == JOB_ID


def test_resolve_requisition_id_from_external_digit() -> None:
    assert resolve_requisition_id({}, "no-match-here", JOB_ID) == JOB_ID


def test_resolve_requisition_id_raises() -> None:
    with pytest.raises(ValueError, match="could not resolve requisition id"):
        resolve_requisition_id({}, "no-match", "not-a-number")


# --- resolve_session_id ------------------------------------------------------


def test_resolve_session_id_from_session_key() -> None:
    creds = {"session": {"session_key": "sk-1"}, "cookies": {}}
    assert resolve_session_id(creds, {}) == "sk-1"


def test_resolve_session_id_from_config() -> None:
    assert resolve_session_id({"session": {}, "cookies": {}}, {"session_id": "cfg"}) == "cfg"


def test_resolve_session_id_none() -> None:
    assert resolve_session_id(None, {}) is None
    assert resolve_session_id({"session": {}, "cookies": {}}, {}) is None


# --- has_session_cookies -----------------------------------------------------


def test_has_session_cookies_variants() -> None:
    assert has_session_cookies(None) is False
    assert has_session_cookies({"cookies": {}}) is False
    assert has_session_cookies({"cookies": {"random": "x"}}) is False
    assert has_session_cookies({"cookies": {"c_user": "1"}}) is True


# --- request_headers ---------------------------------------------------------


def test_request_headers_without_credentials() -> None:
    headers = request_headers(lsd="l", friendly_name="Q", referer="https://ref")
    assert headers["x-fb-lsd"] == "l"
    assert headers["Referer"] == "https://ref"
    assert "Cookie" not in headers


def test_request_headers_with_empty_cookies() -> None:
    headers = request_headers(
        lsd="l",
        friendly_name="Q",
        referer="https://ref",
        credentials={"cookies": {}, "headers": {"X-H": "1"}},
    )
    assert headers["X-H"] == "1"
    assert "Cookie" not in headers


def test_request_headers_with_cookies() -> None:
    headers = request_headers(
        lsd="l",
        friendly_name="Q",
        referer="https://ref",
        credentials={"cookies": {"c_user": "1", "xs": "2"}},
    )
    assert headers["Cookie"] == "c_user=1; xs=2"


# --- extract_application_id --------------------------------------------------


def test_extract_application_id_none_payload() -> None:
    assert extract_application_id({"data": {"xcp_create_application_v2": None}}) is None


def test_extract_application_id_from_app_id() -> None:
    resp = {"data": {"xcp_create_application_v2": {"application_id": 42}}}
    assert extract_application_id(resp) == "42"


def test_extract_application_id_from_consideration() -> None:
    resp = {"data": {"xcp_create_application_v2": {"consideration": {"id": "cid-1"}}}}
    assert extract_application_id(resp) == "cid-1"


def test_extract_application_id_none_when_no_ids() -> None:
    resp = {"data": {"xcp_create_application_v2": {"other": 1}}}
    assert extract_application_id(resp) is None


# --- build_application_state validation ---------------------------------------


def test_build_application_state_requires_name() -> None:
    with pytest.raises(ValueError, match="full_name is required"):
        build_application_state(_detail(), _profile(full_name=""), company="Meta", job_title="TPM")


def test_build_application_state_requires_email() -> None:
    with pytest.raises(ValueError, match="email is required"):
        build_application_state(_detail(), _profile(email=""), company="Meta", job_title="TPM")


def test_build_application_state_single_name_uses_first_as_last() -> None:
    state = build_application_state(
        _detail(),
        ProfileData(full_name="Cher", email="cher@example.com"),
        company="Meta",
        job_title="TPM",
    )
    assert state["candidateFirstName"] == "Cher"
    assert state["candidateLastName"] == "Cher"


# --- _cover_letter_text ------------------------------------------------------


def test_cover_letter_text_explicit() -> None:
    assert (
        _cover_letter_text(_profile(), company="Meta", job_title="TPM", cover_letter=" Hi ") == "Hi"
    )


def test_cover_letter_text_template_empty_returns_none() -> None:
    assert (
        _cover_letter_text(
            _profile(cover_letter_template=""),
            company="Meta",
            job_title="TPM",
            cover_letter=None,
        )
        is None
    )


def test_cover_letter_text_renders_template() -> None:
    result = _cover_letter_text(
        _profile(cover_letter_template="Dear {company} for {job_title}"),
        company="Meta",
        job_title="TPM",
        cover_letter=None,
    )
    assert result == "Dear Meta for TPM"


# --- _yes_no_answer ----------------------------------------------------------


def test_yes_no_answer_yes_no_and_missing() -> None:
    assert _yes_no_answer({"a": "Yes"}, "a") == "0"
    assert _yes_no_answer({"a": "no"}, "a") == "1"
    assert _yes_no_answer({"a": "maybe"}, "a") is None
    assert _yes_no_answer({"a": ""}, "a") is None
    assert _yes_no_answer({}, "a") is None


# --- _drop_empty -------------------------------------------------------------


def test_drop_empty_removes_blanks() -> None:
    cleaned = _drop_empty({"a": None, "b": "  ", "c": [], "d": "keep", "e": [1], "f": False})
    assert cleaned == {"d": "keep", "e": [1], "f": False}


# --- parse_job_detail_response errors ----------------------------------------


def test_parse_job_detail_response_missing_data() -> None:
    with pytest.raises(ValueError, match="missing data"):
        parse_job_detail_response({"data": "not-a-dict"}, requisition_id=JOB_ID)


def test_parse_job_detail_response_missing_job() -> None:
    with pytest.raises(ValueError, match="xcp_requisition_job_description"):
        parse_job_detail_response(
            {"data": {"xcp_requisition_job_description": None}}, requisition_id=JOB_ID
        )


def test_parse_job_detail_response_missing_title() -> None:
    with pytest.raises(ValueError, match="missing title"):
        parse_job_detail_response(
            {"data": {"xcp_requisition_job_description": {"title": ""}}},
            requisition_id=JOB_ID,
        )


def test_parse_job_detail_response_defaults_requisition_id() -> None:
    detail = parse_job_detail_response(
        {"data": {"xcp_requisition_job_description": {"title": "T"}}},
        requisition_id=JOB_ID,
    )
    assert detail.requisition_id == JOB_ID


# --- _string_list / _item_list / _html_blob ----------------------------------


def test_string_list_variants() -> None:
    assert _string_list("not-a-list") == ()
    assert _string_list(["a", "", "  b  ", 5]) == ("a", "b", "5")


def test_item_list_variants() -> None:
    assert _item_list("not-a-list") == ()
    assert _item_list([{"item": "x"}, {"item": ""}, "not-dict", {"other": 1}]) == ("x",)


def test_html_blob_variants() -> None:
    assert _html_blob(123) == ""
    assert _html_blob("   ") == ""
    assert _html_blob("plain text") == "plain text"
    assert _html_blob('{"__html": "<p>hi</p>"}') == "<p>hi</p>"
    # Malformed JSON starting with { -> returned raw.
    assert _html_blob("{not json") == "{not json"
    # Valid JSON object without __html string -> returned raw text.
    assert _html_blob('{"other": 1}') == '{"other": 1}'
