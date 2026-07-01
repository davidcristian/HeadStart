"""Map profile answers to Workday questionnaire response entries."""

from __future__ import annotations

import re
from typing import Any

from app.schemas.profile import ProfileData

_WORKDAY_ID_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)


def flatten_questions(questionnaire: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map question id -> question payload, including branching follow-ups."""
    flattened: dict[str, dict[str, Any]] = {}

    def walk(questions: list[dict[str, Any]]) -> None:
        for question in questions:
            if not isinstance(question, dict):
                continue
            question_id = question.get("id")
            if isinstance(question_id, str) and question_id:
                flattened[question_id] = question
            for answer in question.get("possibleAnswers") or []:
                if not isinstance(answer, dict):
                    continue
                branch = answer.get("branchingQuestion")
                if isinstance(branch, dict):
                    walk([branch])

    questions = questionnaire.get("questions")
    if isinstance(questions, list):
        walk(questions)
    return flattened


def build_questionnaire_answers(
    questionnaire: dict[str, Any],
    profile: ProfileData,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Map profile answers to Workday questionnaireAnswers entries."""
    questions = flatten_questions(questionnaire)
    answer_map = _profile_answer_map(profile, config)
    built: list[dict[str, Any]] = []
    missing_required: list[str] = []

    for question_id, question in questions.items():
        raw_value = answer_map.get(question_id)
        if raw_value is None:
            if question.get("required"):
                missing_required.append(question_id)
            continue
        entry = _answer_entry(question, raw_value)
        if entry is not None:
            built.append(entry)

    return built, missing_required


def _profile_answer_map(profile: ProfileData, config: dict[str, Any]) -> dict[str, str]:
    """Merge profile answers with optional config aliases."""
    merged = dict(profile.answers)
    aliases = config.get("questionnaire_answers")
    if isinstance(aliases, dict):
        for key, value in aliases.items():
            if value:
                merged[str(key)] = str(value)
    return {str(key): str(value) for key, value in merged.items() if value}


def _answer_entry(question: dict[str, Any], raw_value: str) -> dict[str, Any] | None:
    """Convert one profile answer into a Workday questionnaireAnswers item."""
    question_id = str(question.get("id") or "")
    if not question_id:
        return None
    qtype = _question_type(question)
    base = {"questionItem": {"id": question_id}}

    if qtype == "text":
        return {**base, "answerText": raw_value}

    if qtype == "date":
        return {**base, "answerDate": raw_value}

    if qtype == "numeric":
        try:
            numeric = int(raw_value)
        except ValueError:
            return None
        if numeric <= 0:
            return None
        return {**base, "answerNumeric": numeric}

    if qtype in {"single", "multi"}:
        answer_ids = _resolve_choice_ids(question, raw_value, multi=qtype == "multi")
        if not answer_ids:
            return None
        return {**base, "questionMultipleChoiceAnswers": answer_ids}

    return {**base, "answerText": raw_value}


def _question_type(question: dict[str, Any]) -> str:
    descriptor = ""
    qtype = question.get("type")
    if isinstance(qtype, dict):
        descriptor = str(qtype.get("descriptor") or "").lower()
    if "multi" in descriptor and "choice" in descriptor:
        return "multi"
    if "single" in descriptor and "choice" in descriptor:
        return "single"
    if "numeric" in descriptor or "number" in descriptor:
        return "numeric"
    if "date" in descriptor:
        return "date"
    if "upload" in descriptor:
        return "upload"
    if "text" in descriptor:
        return "text"
    if question.get("possibleAnswers"):
        return "single"
    return "text"


def _resolve_choice_ids(question: dict[str, Any], raw_value: str, *, multi: bool) -> list[str]:
    """Resolve choice answer ids from a Workday id or human-readable label."""
    if multi:
        values = [part.strip() for part in raw_value.split(",") if part.strip()]
    else:
        values = [raw_value]
    resolved: list[str] = []
    possible = [
        answer for answer in (question.get("possibleAnswers") or []) if isinstance(answer, dict)
    ]
    for value in values:
        if _WORKDAY_ID_RE.match(value):
            resolved.append(value)
            continue
        match = _match_answer_text(possible, value)
        if match:
            resolved.append(str(match["id"]))
    return resolved


def _match_answer_text(possible: list[dict[str, Any]], value: str) -> dict[str, Any] | None:
    target = value.strip().lower()
    for answer in possible:
        answer_text = str(answer.get("answerText") or "").strip().lower()
        if answer_text and answer_text == target:
            return answer
    return None
