"""Fetch Uber Careers screening questions for an application."""

from __future__ import annotations

from typing import Any

from app.appliers.adapters.uber_careers_common import (
    _POSTING_TYPE_EXTERNAL,
    api_headers,
    api_url,
    apply_form_url,
)
from app.scrapers.http import HttpClient


def fetch_additional_questions(
    http: HttpClient,
    *,
    job_id: int,
    locale: str,
    locale_path: str,
) -> list[dict[str, Any]]:
    """Load job-specific screening questions from the careers apply API."""
    referer = apply_form_url(job_id, locale_path=locale_path)
    payload = http.post_json(
        api_url("getAdditionalQuestionsForJob", locale=locale),
        json={"jobId": job_id, "postingType": _POSTING_TYPE_EXTERNAL},
        headers=api_headers(referer=referer),
    )
    if not isinstance(payload, dict):
        raise ValueError("uber_careers questions API returned unexpected payload")
    if payload.get("status") != "success":
        data = payload.get("data")
        message = data.get("message") if isinstance(data, dict) else payload
        raise ValueError(f"uber_careers questions API failed: {message}")
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    questions = data.get("additionalQuestions")
    if not isinstance(questions, list):
        return []
    return [item for item in questions if isinstance(item, dict)]


def normalize_question(item: dict[str, Any]) -> dict[str, Any]:
    """Flatten one API question row into applier-friendly ids."""
    question_id = _question_id(item)
    form_key = _form_question_id(item, question_id=question_id)
    options = item.get("options")
    return {
        "question_id": question_id,
        "form_question_id": form_key,
        "question": str(item.get("question") or item.get("title") or "").strip(),
        "options": [str(option) for option in options] if isinstance(options, list) else [],
        "application_section": str(item.get("applicationSection") or "").strip(),
        "raw": item,
    }


def build_question_responses(
    questions: list[dict[str, Any]],
    answers: dict[str, str],
) -> list[dict[str, str]]:
    """Map profile answers onto Uber additionalQuestionsResponses entries."""
    responses: list[dict[str, str]] = []
    for item in questions:
        normalized = normalize_question(item)
        question_id = normalized["question_id"]
        form_key = normalized["form_question_id"]
        if not question_id or not form_key:
            continue
        raw_answer = _lookup_answer(answers, question_id=question_id, form_key=form_key)
        if raw_answer is None:
            continue
        answer = _match_option(raw_answer, normalized["options"])
        responses.append({"questionID": question_id, "answer": answer})
    return responses


def missing_required_answers(
    questions: list[dict[str, Any]],
    answers: dict[str, str],
) -> list[str]:
    """Return question ids that have no mapped profile answer."""
    missing: list[str] = []
    for item in questions:
        normalized = normalize_question(item)
        question_id = normalized["question_id"]
        form_key = normalized["form_question_id"]
        if not question_id or not form_key:
            continue
        if _lookup_answer(answers, question_id=question_id, form_key=form_key) is None:
            label = normalized["question"] or question_id
            missing.append(label)
    return missing


def _question_id(item: dict[str, Any]) -> str:
    question_id = item.get("questionID")
    if question_id:
        return str(question_id).strip()
    nested = item.get("questionId")
    if isinstance(nested, dict):
        value = nested.get("value")
        if value:
            return str(value).strip()
    return ""


def _form_question_id(item: dict[str, Any], *, question_id: str) -> str:
    form_key = item.get("formQuestionId")
    if form_key:
        return str(form_key).strip()
    field_name = item.get("fieldName")
    if field_name:
        return str(field_name).strip()
    return question_id


def _lookup_answer(
    answers: dict[str, str],
    *,
    question_id: str,
    form_key: str,
) -> str | None:
    for key in (
        form_key,
        f"uber_{question_id}",
        f"question_{question_id}",
        question_id,
    ):
        value = answers.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return None


def _match_option(answer: str, options: list[str]) -> str:
    if not options:
        return answer
    lowered = answer.lower()
    for option in options:
        if option.lower() == lowered:
            return option
    return answer
