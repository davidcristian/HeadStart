"""Tests for SmartRecruiters screening-answer mapping."""

from app.appliers.adapters.smartrecruiters_questions import (
    _build_question_answer,
    _map_field_answer,
    _resolve_option_id,
    build_screening_answers,
    missing_required_answers,
    profile_answer_for_question,
)


def test_profile_answer_for_question_prefers_sr_key_then_raw_then_prefixed() -> None:
    assert profile_answer_for_question({"sr_q1": "a"}, "q1") == "a"
    assert profile_answer_for_question({"q1": "b"}, "q1") == "b"
    assert profile_answer_for_question({"question_q1": "c"}, "q1") == "c"
    assert profile_answer_for_question({}, "q1") is None


def test_build_screening_answers_skips_none_results() -> None:
    configuration = {"questions": [{"id": "", "fields": []}, {"id": "q1"}]}
    assert build_screening_answers(configuration, {}) == []


def test_build_question_answer_requires_id() -> None:
    assert _build_question_answer({"fields": [{"id": "value", "type": "TEXT"}]}, {"": "x"}) is None


def test_build_question_answer_requires_fields_list() -> None:
    assert _build_question_answer({"id": "q1", "fields": "nope"}, {"sr_q1": "x"}) is None
    assert _build_question_answer({"id": "q1", "fields": []}, {"sr_q1": "x"}) is None


def test_build_question_answer_all_information_fields() -> None:
    question = {"id": "q1", "fields": [{"id": "v", "type": "INFORMATION"}]}
    assert _build_question_answer(question, {"sr_q1": "x"}) is None


def test_build_question_answer_missing_raw_answer() -> None:
    question = {"id": "q1", "fields": [{"id": "value", "type": "INPUT_TEXT"}]}
    assert _build_question_answer(question, {}) is None


def test_build_question_answer_skips_non_dict_field_and_none_mapped() -> None:
    question = {
        "id": "q1",
        "fields": [
            "not a dict",
            {"id": "value", "type": "CHECKBOX"},
        ],
    }
    # "no" maps to None for CHECKBOX, leaving no record fields.
    assert _build_question_answer(question, {"sr_q1": "no"}) is None


def test_build_question_answer_builds_records() -> None:
    question = {"id": "q1", "fields": [{"id": "value", "type": "INPUT_TEXT"}]}
    result = _build_question_answer(question, {"sr_q1": "hello"})
    assert result == {"id": "q1", "records": [{"fields": {"value": ["hello"]}}]}


def test_map_field_answer_blank_returns_none() -> None:
    assert _map_field_answer("INPUT_TEXT", "   ", []) is None


def test_map_field_answer_checkbox_falsey_and_options() -> None:
    assert _map_field_answer("CHECKBOX", "no", []) is None
    assert _map_field_answer("CHECKBOX", "yes", [{"id": "opt-9"}]) == ["opt-9"]
    assert _map_field_answer("CHECKBOX", "yes", []) == ["1"]


def test_map_field_answer_radio_and_multi_select() -> None:
    options = [{"id": "1", "label": "Yes"}, {"id": "0", "label": "No"}]
    assert _map_field_answer("RADIO", "Yes", options) == ["1"]
    assert _map_field_answer("MULTI_SELECT", "Yes, No", options) == ["1", "0"]


def test_map_field_answer_text_types() -> None:
    assert _map_field_answer("TEXTAREA", "hello", []) == ["hello"]


def test_map_field_answer_json_dict_is_normalized() -> None:
    assert _map_field_answer("UNKNOWN", '{"a": 1}', []) == ['{"a": 1}']


def test_map_field_answer_invalid_json_falls_back_to_raw() -> None:
    assert _map_field_answer("UNKNOWN", "{not json", []) == ["{not json"]


def test_map_field_answer_plain_string_default() -> None:
    assert _map_field_answer("UNKNOWN", "plain", []) == ["plain"]


def test_resolve_option_id_by_id_label_and_fallback() -> None:
    options = [{"id": "1", "label": "Yes"}, "not a dict", {"id": "2", "label": "No"}]
    assert _resolve_option_id("1", options) == "1"
    assert _resolve_option_id("no", options) == "2"
    assert _resolve_option_id("Maybe", options) == "Maybe"


def test_missing_required_answers_skips_no_id_no_fields_and_not_required() -> None:
    configuration = {
        "questions": [
            {"label": "no id"},
            {"id": "q1", "fields": "nope"},
            {"id": "q2", "fields": [{"required": False, "type": "TEXT"}]},
            {"id": "q3", "fields": [{"id": "value", "required": True, "type": "INPUT_TEXT"}]},
        ]
    }
    assert missing_required_answers(configuration, {}) == ["q3"]
    assert missing_required_answers(configuration, {"sr_q3": "answered"}) == []
