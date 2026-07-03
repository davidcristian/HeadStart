"""Map profile answers onto SmartRecruiters screening question payloads."""

from __future__ import annotations

import json
from typing import Any

from app.appliers.adapters.smartrecruiters_configuration import configuration_questions


def answer_key(question_id: str) -> str:
    """Profile answers key for a SmartRecruiters question id."""
    return f"sr_{question_id}"


def profile_answer_for_question(profile_answers: dict[str, str], question_id: str) -> str | None:
    """Resolve a profile answer using SmartRecruiters-specific or raw keys."""
    for key in (answer_key(question_id), question_id, f"question_{question_id}"):
        value = profile_answers.get(key)
        if value:
            return value
    return None


def build_screening_answers(
    configuration: dict[str, Any] | None,
    profile_answers: dict[str, str],
) -> list[dict[str, Any]]:
    """Build the SmartRecruiters `answers` array from posting configuration."""
    answers: list[dict[str, Any]] = []
    for question in configuration_questions(configuration or {}):
        built = _build_question_answer(question, profile_answers)
        if built is not None:
            answers.append(built)
    return answers


def missing_required_answers(
    configuration: dict[str, Any] | None,
    profile_answers: dict[str, str],
) -> list[str]:
    """Question ids still unanswered after mapping profile answers."""
    missing: list[str] = []
    for question in configuration_questions(configuration or {}):
        question_id = str(question.get("id") or "")
        if not question_id:
            continue
        fields = question.get("fields")
        if not isinstance(fields, list):
            continue
        if not any(
            isinstance(field, dict)
            and field.get("required")
            and field.get("type") not in {"INFORMATION"}
            for field in fields
        ):
            continue
        if _build_question_answer(question, profile_answers) is None:
            missing.append(question_id)
    return missing


def _build_question_answer(
    question: dict[str, Any],
    profile_answers: dict[str, str],
) -> dict[str, Any] | None:
    question_id = str(question.get("id") or "")
    if not question_id:
        return None

    fields = question.get("fields")
    if not isinstance(fields, list) or not fields:
        return None

    if all(isinstance(field, dict) and field.get("type") == "INFORMATION" for field in fields):
        return None

    raw_answer = profile_answer_for_question(profile_answers, question_id)
    if raw_answer is None:
        return None

    record_fields: dict[str, list[str]] = {}
    for field in fields:
        if not isinstance(field, dict):
            continue
        field_id = str(field.get("id") or "value")
        field_type = str(field.get("type") or "").upper()
        values = field.get("values")
        option_values = values if isinstance(values, list) else []
        mapped = _map_field_answer(field_type, raw_answer, option_values)
        if mapped is None:
            continue
        record_fields[field_id] = mapped

    if not record_fields:
        return None

    return {
        "id": question_id,
        "records": [{"fields": record_fields}],
    }


def _map_field_answer(
    field_type: str,
    raw_answer: str,
    options: list[dict[str, Any]],
) -> list[str] | None:
    cleaned = raw_answer.strip()
    if not cleaned:
        return None

    if field_type == "CHECKBOX":
        if cleaned.lower() in {"0", "false", "no", "unchecked"}:
            return None
        if options:
            option_id = str(options[0].get("id") or "1")
            return [option_id]
        return ["1"]

    if field_type in {"RADIO", "SINGLE_SELECT"}:
        return [_resolve_option_id(cleaned, options)]

    if field_type == "MULTI_SELECT":
        parts = [part.strip() for part in cleaned.split(",") if part.strip()]
        return [_resolve_option_id(part, options) for part in parts]

    if field_type in {"INPUT_TEXT", "TEXTAREA", "CURRENCY"}:
        return [cleaned]

    if cleaned.startswith("{"):
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return [cleaned]
        return [json.dumps(parsed)]
    return [cleaned]


def _resolve_option_id(raw_value: str, options: list[dict[str, Any]]) -> str:
    """Match a profile answer to a SmartRecruiters option id by id or label."""
    lowered = raw_value.lower()
    for option in options:
        if not isinstance(option, dict):
            continue
        option_id = str(option.get("id") or "")
        label = str(option.get("label") or "")
        if raw_value == option_id or lowered == label.lower():
            return option_id
    return raw_value
