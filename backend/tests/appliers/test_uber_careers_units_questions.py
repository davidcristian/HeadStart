"""Unit-level branch coverage for the Uber Careers questions helpers."""

import httpx
import pytest

from app.appliers.adapters.uber_careers_questions import (
    build_question_responses,
    fetch_additional_questions,
    missing_required_answers,
    normalize_question,
)
from tests.conftest import make_http_client

# --- uber_careers_questions ----------------------------------------------


def _questions_client(payload: object) -> object:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return make_http_client(handler)


def _fetch(payload: object) -> object:
    return fetch_additional_questions(
        _questions_client(payload),  # type: ignore[arg-type]
        job_id=1,
        locale="en",
        locale_path="us/en",
    )


def test_fetch_questions_rejects_non_dict_payload() -> None:
    with pytest.raises(ValueError, match="unexpected payload"):
        _fetch(["nope"])


def test_fetch_questions_reports_dict_error_message() -> None:
    with pytest.raises(ValueError, match="down for maintenance"):
        _fetch({"status": "error", "data": {"message": "down for maintenance"}})


def test_fetch_questions_reports_raw_payload_when_no_message() -> None:
    with pytest.raises(ValueError, match="questions API failed"):
        _fetch({"status": "error", "data": "opaque"})


def test_fetch_questions_returns_empty_when_data_not_dict() -> None:
    assert _fetch({"status": "success", "data": "nope"}) == []


def test_fetch_questions_returns_empty_when_questions_not_list() -> None:
    assert _fetch({"status": "success", "data": {"additionalQuestions": "nope"}}) == []


def test_fetch_questions_drops_non_dict_rows() -> None:
    payload = {
        "status": "success",
        "data": {"additionalQuestions": [{"questionID": "Q1"}, "junk"]},
    }
    assert _fetch(payload) == [{"questionID": "Q1"}]


def test_normalize_question_prefers_flat_question_id() -> None:
    assert normalize_question({"questionID": " Q7 "})["question_id"] == "Q7"


def test_normalize_question_empty_when_no_id() -> None:
    assert normalize_question({"question": "hi"})["question_id"] == ""


def test_normalize_question_empty_when_nested_value_blank() -> None:
    # Nested questionId dict present but its value is falsy -> falls to "" (112->114).
    assert normalize_question({"questionId": {"value": ""}})["question_id"] == ""


def test_normalize_question_uses_field_name_fallback() -> None:
    normalized = normalize_question({"questionID": "Q7", "fieldName": " screening "})
    assert normalized["form_question_id"] == "screening"


def test_normalize_question_form_id_defaults_to_question_id() -> None:
    normalized = normalize_question({"questionID": "Q7"})
    assert normalized["form_question_id"] == "Q7"


def test_is_required_string_flag() -> None:
    assert normalize_question({"questionID": "Q7", "required": "true"})["required"] is True


def test_is_required_bool_false_continues_scan() -> None:
    # required=False (bool, not True) must not short-circuit; isRequired=True wins.
    normalized = normalize_question({"questionID": "Q7", "required": False, "isRequired": True})
    assert normalized["required"] is True


def test_build_question_responses_skips_unidentified_and_unanswered() -> None:
    questions = [
        {"question": "no id here"},
        {"questionID": "Q7", "formQuestionId": "fq7"},
    ]
    # No answer for Q7 either -> both skipped.
    assert build_question_responses(questions, {}) == []


def test_build_question_responses_matches_option_case_insensitively() -> None:
    question = {
        "questionID": "Q7",
        "formQuestionId": "fq7",
        "options": ["Yes, I do", "No"],
    }
    responses = build_question_responses([question], {"fq7": "yes, i do"})
    assert responses == [{"questionID": "Q7", "answer": "Yes, I do"}]


def test_build_question_responses_free_text_without_options() -> None:
    # No options list -> _match_option returns the raw answer (line 159).
    question = {"questionID": "Q7", "formQuestionId": "fq7"}
    responses = build_question_responses([question], {"fq7": "free text"})
    assert responses == [{"questionID": "Q7", "answer": "free text"}]


def test_build_question_responses_keeps_answer_without_matching_option() -> None:
    question = {
        "questionID": "Q7",
        "formQuestionId": "fq7",
        "options": ["A", "B"],
    }
    responses = build_question_responses([question], {"fq7": "C"})
    assert responses == [{"questionID": "Q7", "answer": "C"}]


def test_missing_required_skips_unidentified_required_question() -> None:
    # required but no resolvable id/form-key -> skipped, not reported missing.
    questions = [{"question": "no id", "required": True}]
    assert missing_required_answers(questions, {}) == []
