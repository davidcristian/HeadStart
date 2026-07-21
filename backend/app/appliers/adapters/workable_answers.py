"""Custom-question and structured-history helpers for Workable apply payloads."""

from __future__ import annotations

from typing import Any

from app.schemas.profile import ProfileData

_STANDARD_FIELD_IDS = frozenset(
    {
        "firstname",
        "lastname",
        "email",
        "phone",
        "headline",
        "summary",
        "address",
        "cover_letter",
        "resume",
        "avatar",
        "education",
        "experience",
        "education_entries",
        "experience_entries",
        "skills",
    }
)

_TRUTHY = frozenset({"1", "true", "yes", "y", "on"})


def standard_field_ids() -> frozenset[str]:
    """Top-level candidate attribute ids (everything else becomes answers)."""
    return _STANDARD_FIELD_IDS


def build_answers(
    profile: ProfileData,
    *,
    form_fields: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Map profile links/answers onto Workable custom form questions."""
    by_id = {
        str(field.get("id") or "").strip(): field
        for field in form_fields
        if str(field.get("id") or "").strip()
    }
    answers: list[dict[str, Any]] = []
    seen: set[str] = set()

    for field_id, field in by_id.items():
        if field_id in _STANDARD_FIELD_IDS:
            continue
        raw = _answer_raw_for_field(profile, field_id=field_id, field=field, config=config)
        if raw is None:
            continue
        answers.append(_format_answer(field_id, field, raw))
        seen.add(field_id)

    for key, value in profile.answers.items():
        cleaned_key = key.strip()
        if not cleaned_key or cleaned_key in seen or cleaned_key in _STANDARD_FIELD_IDS:
            continue
        field = by_id.get(cleaned_key) or {"id": cleaned_key, "type": "text", "label": cleaned_key}
        answers.append(_format_answer(cleaned_key, field, value))
    return answers


def answer_present(answer: object) -> bool:
    """True when a Workable answers[] entry carries a usable value."""
    if not isinstance(answer, dict):
        return False
    if "checked" in answer:
        return bool(answer.get("checked"))
    for key in ("body", "date"):
        value = answer.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False


def experience_entries(profile: ProfileData) -> list[dict[str, Any]]:
    """Map profile work history into Workable ``experience_entries``."""
    entries: list[dict[str, Any]] = []
    for item in profile.work_experience:
        title = item.job_title.strip()
        company = item.company.strip()
        if not title and not company:
            continue
        entry: dict[str, Any] = {
            "title": title,
            "company": company,
            "summary": item.description.strip(),
            "current": item.is_current,
        }
        start = _year_month(item.start_year, item.start_month)
        end = _year_month(item.end_year, item.end_month)
        if start:
            entry["start_date"] = start
        if end:
            entry["end_date"] = end
        entries.append(entry)
    return entries


def education_entries(profile: ProfileData) -> list[dict[str, Any]]:
    """Map profile education into Workable ``education_entries``."""
    entries: list[dict[str, Any]] = []
    for item in profile.education:
        school = item.school.strip()
        if not school:
            continue
        entry: dict[str, Any] = {
            "school": school,
            "degree": item.degree.strip(),
            "field_of_study": item.field_of_study.strip(),
        }
        if item.start_year:
            entry["start_date"] = f"{item.start_year:04d}-01-01"
        if item.end_year:
            entry["end_date"] = f"{item.end_year:04d}-01-01"
        entries.append(entry)
    return entries


def _answer_raw_for_field(
    profile: ProfileData,
    *,
    field_id: str,
    field: dict[str, Any],
    config: dict[str, Any],
) -> str | None:
    if field_id in profile.answers and str(profile.answers[field_id]).strip():
        return str(profile.answers[field_id]).strip()
    if field_id in config and str(config[field_id]).strip():
        return str(config[field_id]).strip()

    label = str(field.get("label") or "").casefold()
    if "linkedin" in label or field_id.casefold() == "linkedin":
        link = (profile.links.linkedin or "").strip()
        return _ensure_http(link) if link else None
    if "github" in label or field_id.casefold() == "github":
        link = (profile.links.github or "").strip()
        return _ensure_http(link) if link else None
    if "website" in label or "portfolio" in label:
        link = (profile.links.website or "").strip()
        return _ensure_http(link) if link else None
    if field_id == "gdpr":
        # Consent is implied by the user initiating apply; dry-run/live both set it.
        return "true"
    return None


def _format_answer(field_id: str, field: dict[str, Any], raw: str) -> dict[str, Any]:
    label = str(field.get("label") or field_id).strip() or field_id
    field_type = str(field.get("type") or "text").strip().lower()
    answer: dict[str, Any] = {"question_key": field_id, "label": label}
    if field_type in {"boolean", "checkbox"}:
        answer["checked"] = _is_truthy(raw)
        return answer
    if field_type == "date":
        answer["date"] = raw
        return answer
    if field_type == "dropdown":
        choice_id = _dropdown_choice_id(field, raw)
        if choice_id is not None:
            answer["body"] = choice_id
            return answer
    answer["body"] = raw
    return answer


def _dropdown_choice_id(field: dict[str, Any], raw: str) -> str | None:
    choices = field.get("choices") or field.get("options")
    if not isinstance(choices, list):
        return None
    needle = raw.casefold()
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        choice_id = str(choice.get("id") or choice.get("value") or "").strip()
        body = str(choice.get("body") or choice.get("label") or "").strip()
        if needle in {choice_id.casefold(), body.casefold()}:
            return choice_id or body
    return None


def _year_month(year: int | None, month: int | None) -> str | None:
    if year is None:
        return None
    mm = month or 1
    return f"{year:04d}-{mm:02d}-01"


def _ensure_http(url: str) -> str:
    cleaned = url.strip()
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    return f"https://{cleaned.lstrip('/')}"


def _is_truthy(value: str) -> bool:
    return value.strip().casefold() in _TRUTHY
