"""Tests for Ashby API response parsing helpers."""

from app.appliers.adapters.ashby_response import (
    extract_application_id,
    extract_blocked_message,
    extract_error_message,
)


def test_extract_application_id_non_dict_response() -> None:
    assert extract_application_id("nope") is None


def test_extract_application_id_results_not_dict() -> None:
    assert extract_application_id({"results": ["x"]}) is None


def test_extract_application_id_instance_not_dict() -> None:
    assert extract_application_id({"results": {"submittedFormInstance": "x"}}) is None


def test_extract_application_id_missing_id_returns_none() -> None:
    assert extract_application_id({"results": {"submittedFormInstance": {}}}) is None


def test_extract_blocked_message_non_dict_response() -> None:
    assert extract_blocked_message("nope") is None


def test_extract_blocked_message_results_not_dict() -> None:
    assert extract_blocked_message({"results": ["x"]}) is None


def test_extract_blocked_message_not_blocked() -> None:
    assert extract_blocked_message({"results": {"formMessages": {"blocked": False}}}) is None


def test_extract_blocked_message_default_when_no_html() -> None:
    message = extract_blocked_message(
        {"results": {"formMessages": {"blocked": True, "blockMessageForCandidateHtml": "  "}}}
    )
    assert message == "ashby blocked this application due to configured application limits"


def test_extract_error_message_from_error_info() -> None:
    assert extract_error_message({"errorInfo": {"message": "boom"}}) == "boom"


def test_extract_error_message_from_errors_list() -> None:
    assert extract_error_message({"errors": ["a", "b"]}) == "a; b"


def test_extract_error_message_ignores_empty_error_info_message() -> None:
    assert (
        extract_error_message({"errorInfo": {"message": ""}, "errors": ["fallback"]}) == "fallback"
    )


def test_extract_error_message_default() -> None:
    assert extract_error_message({}) == "ashby apply rejected the submission"
