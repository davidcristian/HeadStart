"""Unit tests for Workday questionnaire answer mapping."""

from typing import Any

from app.appliers.adapters.workday_questionnaire_answers import (
    _answer_entry,
    build_questionnaire_answers,
    flatten_questions,
)
from app.schemas.profile import ProfileData


def _question(qid: str, descriptor: str, **extra: Any) -> dict[str, Any]:
    return {"id": qid, "type": {"descriptor": descriptor}, **extra}


def test_flatten_questions_ignores_non_dict_entries() -> None:
    questionnaire = {
        "questions": [
            "not-a-dict",
            {"id": "", "possibleAnswers": []},
            {"possibleAnswers": ["not-a-dict", {"branchingQuestion": "nope"}]},
            {
                "id": "parent",
                "possibleAnswers": [
                    {"branchingQuestion": {"id": "child"}},
                ],
            },
        ]
    }
    flattened = flatten_questions(questionnaire)
    assert set(flattened) == {"parent", "child"}


def test_flatten_questions_handles_missing_questions_list() -> None:
    assert flatten_questions({}) == {}
    assert flatten_questions({"questions": "nope"}) == {}


def test_build_answers_maps_config_aliases_and_skips_falsy() -> None:
    questionnaire = {"questions": [_question("q-text", "Text")]}
    answers, missing = build_questionnaire_answers(
        questionnaire,
        ProfileData(answers={}),
        {"questionnaire_answers": {"q-text": "aliased", "ignored": ""}},
    )
    assert missing == []
    assert answers == [{"questionItem": {"id": "q-text"}, "answerText": "aliased"}]


def test_build_answers_ignores_non_dict_aliases() -> None:
    questionnaire = {"questions": [_question("q-text", "Text")]}
    answers, _ = build_questionnaire_answers(
        questionnaire,
        ProfileData(answers={"q-text": "value"}),
        {"questionnaire_answers": "not-a-dict"},
    )
    assert answers == [{"questionItem": {"id": "q-text"}, "answerText": "value"}]


def test_build_answers_records_missing_required_and_skips_optional() -> None:
    questionnaire = {
        "questions": [
            _question("q-req", "Text", required=True),
            _question("q-opt", "Text"),
        ]
    }
    answers, missing = build_questionnaire_answers(questionnaire, ProfileData(answers={}), {})
    assert answers == []
    assert missing == ["q-req"]


def test_build_answers_drops_entry_when_conversion_returns_none() -> None:
    questionnaire = {"questions": [_question("q-num", "Numeric")]}
    answers, missing = build_questionnaire_answers(
        questionnaire, ProfileData(answers={"q-num": "not-a-number"}), {}
    )
    assert answers == []
    assert missing == []


def test_answer_entry_date_type() -> None:
    questionnaire = {"questions": [_question("q-date", "Date")]}
    answers, _ = build_questionnaire_answers(
        questionnaire, ProfileData(answers={"q-date": "2024-01-01"}), {}
    )
    assert answers == [{"questionItem": {"id": "q-date"}, "answerDate": "2024-01-01"}]


def test_answer_entry_numeric_valid_and_non_positive() -> None:
    questionnaire = {"questions": [_question("q-num", "Numeric")]}
    valid, _ = build_questionnaire_answers(questionnaire, ProfileData(answers={"q-num": "5"}), {})
    assert valid == [{"questionItem": {"id": "q-num"}, "answerNumeric": 5}]

    zero, _ = build_questionnaire_answers(questionnaire, ProfileData(answers={"q-num": "0"}), {})
    assert zero == []


def test_answer_entry_upload_type_falls_back_to_text() -> None:
    questionnaire = {"questions": [_question("q-up", "File Upload")]}
    answers, _ = build_questionnaire_answers(
        questionnaire, ProfileData(answers={"q-up": "resume"}), {}
    )
    assert answers == [{"questionItem": {"id": "q-up"}, "answerText": "resume"}]


def test_answer_entry_infers_single_from_possible_answers_without_type() -> None:
    questionnaire = {
        "questions": [
            {
                "id": "q-choice",
                "possibleAnswers": [{"id": "ans-yes", "answerText": "Yes"}],
            }
        ]
    }
    answers, _ = build_questionnaire_answers(
        questionnaire, ProfileData(answers={"q-choice": "Yes"}), {}
    )
    assert answers == [
        {"questionItem": {"id": "q-choice"}, "questionMultipleChoiceAnswers": ["ans-yes"]}
    ]


def test_answer_entry_defaults_to_text_without_type_or_answers() -> None:
    questionnaire = {"questions": [{"id": "q-plain"}]}
    answers, _ = build_questionnaire_answers(
        questionnaire, ProfileData(answers={"q-plain": "free text"}), {}
    )
    assert answers == [{"questionItem": {"id": "q-plain"}, "answerText": "free text"}]


def test_answer_entry_single_choice_no_match_returns_none() -> None:
    questionnaire = {
        "questions": [
            {
                "id": "q-choice",
                "type": {"descriptor": "Single Choice"},
                "possibleAnswers": [
                    "not-a-dict",
                    {"id": "ans-yes", "answerText": ""},
                    {"id": "ans-no", "answerText": "No"},
                ],
            }
        ]
    }
    answers, _ = build_questionnaire_answers(
        questionnaire, ProfileData(answers={"q-choice": "Maybe"}), {}
    )
    assert answers == []


def test_answer_entry_multi_choice_by_workday_id_and_label() -> None:
    questionnaire = {
        "questions": [
            {
                "id": "q-multi",
                "type": {"descriptor": "Multiple Choice"},
                "possibleAnswers": [{"id": "ans-a", "answerText": "Alpha"}],
            }
        ]
    }
    wid = "f1e2d3c4b5a697887766554433221100"
    answers, _ = build_questionnaire_answers(
        questionnaire,
        ProfileData(answers={"q-multi": f"Alpha, {wid},  "}),
        {},
    )
    assert answers == [
        {
            "questionItem": {"id": "q-multi"},
            "questionMultipleChoiceAnswers": ["ans-a", wid],
        }
    ]


def test_answer_entry_without_question_id_returns_none() -> None:
    assert _answer_entry({"type": {"descriptor": "Text"}}, "value") is None


def test_answer_entry_type_dict_missing_descriptor() -> None:
    questionnaire = {"questions": [{"id": "q-x", "type": {}}]}
    answers, _ = build_questionnaire_answers(
        questionnaire, ProfileData(answers={"q-x": "value"}), {}
    )
    assert answers == [{"questionItem": {"id": "q-x"}, "answerText": "value"}]
