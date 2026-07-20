"""Build Rippling public-board application payloads from a profile."""

from __future__ import annotations

from typing import Any

from app.appliers.resume import resume_meta_for_payload
from app.appliers.text import split_name
from app.schemas.profile import ProfileData, ResumeFile

# Built-in basic-question oids the careers UI maps from the candidate form.
_PROFILE_OIDS = frozenset(
    {
        "first_name",
        "last_name",
        "email",
        "phone_number",
        "location",
        "linkedin_link",
        "website_link",
        "current_company",
        "pronouns",
        "nickname",
        "resume",
        "cover_letter",
        "country_code",
    }
)


def basic_questions(job_detail: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return ``activeJobApplication.basicQuestions`` when present."""
    if not isinstance(job_detail, dict):
        return []
    active = job_detail.get("activeJobApplication")
    if not isinstance(active, dict):
        return []
    questions = active.get("basicQuestions")
    return questions if isinstance(questions, list) else []


def required_question_oids(job_detail: dict[str, Any] | None) -> list[str]:
    """Required basic-question oids from the job detail payload."""
    oids: list[str] = []
    for question in basic_questions(job_detail):
        if not isinstance(question, dict) or not question.get("required"):
            continue
        oid = str(question.get("oid") or "").strip()
        if oid:
            oids.append(oid)
    return oids


def build_application_form_response(
    profile: ProfileData,
    *,
    config: dict[str, Any],
    company: str,
    cover_letter: str | None,
    resume_file: ResumeFile | None,
    resume_url: str | None = None,
    resume_content_type: str | None = None,
    cover_letter_url: str | None = None,
    cover_letter_content_type: str | None = None,
    include_resume_meta: bool = True,
) -> dict[str, Any]:
    """Map profile fields into Rippling's ``applicationFormResponse`` object."""
    first_name, last_name = split_name(profile.full_name)
    form: dict[str, Any] = {
        "first_name": first_name,
        "last_name": last_name or first_name,
        "email": profile.email.strip(),
        "phone_number": profile.phone.strip(),
        "location": _location(profile, config),
        "timezone": str(config.get("timezone") or "UTC"),
        "jobSite": str(config.get("job_site") or config.get("jobSite") or "ats"),
    }
    country = str(config.get("country_code") or profile.answers.get("country_code") or "").strip()
    if country:
        form["country_code"] = country

    linkedin = (profile.links.linkedin or "").strip()
    if linkedin:
        form["linkedin_link"] = _ensure_http(linkedin)
    website = (profile.links.website or "").strip()
    if website:
        form["website_link"] = _ensure_http(website)

    current_company = _current_company(profile, config, company)
    if current_company:
        form["current_company"] = current_company

    pronoun = str(config.get("pronoun_strategy") or profile.answers.get("pronouns") or "").strip()
    if pronoun:
        form["pronounStrategy"] = pronoun
        custom = str(profile.answers.get("pronouns_custom") or "").strip()
        if custom:
            form["pronounCustomValue"] = custom

    if resume_url:
        form["resume"] = resume_url
        form["resumeFileExtension"] = resume_content_type or (
            resume_file.content_type if resume_file else "application/pdf"
        )
    elif include_resume_meta:
        meta = resume_meta_for_payload(resume_file)
        if meta is not None:
            form["resume_file"] = meta

    if cover_letter_url:
        form["cover_letter"] = cover_letter_url
        form["coverLetterFileExtension"] = cover_letter_content_type or "text/plain"
    elif cover_letter and cover_letter.strip():
        form["cover_letter_text"] = cover_letter.strip()

    # Allow profile.answers to fill remaining known oids (screening shortcuts).
    for key, value in profile.answers.items():
        oid = key.removeprefix("rippling_").strip()
        if oid in _PROFILE_OIDS and oid not in form and str(value).strip():
            form[oid] = str(value).strip()

    return form


def missing_required_fields(
    form: dict[str, Any], required_oids: list[str], *, live: bool
) -> list[str]:
    """Return required oids that are still empty in the form response."""
    missing: list[str] = []
    for oid in required_oids:
        if oid == "resume":
            if live and not form.get("resume"):
                missing.append(oid)
            elif not live and not (form.get("resume") or form.get("resume_file")):
                missing.append(oid)
            continue
        if oid == "cover_letter":
            if live and not form.get("cover_letter"):
                # Optional on most boards; only require when the job marks it required.
                missing.append(oid)
            continue
        if oid == "phone_number":
            if not str(form.get("phone_number") or "").strip():
                missing.append(oid)
            continue
        if not str(form.get(oid) or "").strip():
            missing.append(oid)
    return missing


def build_apply_payload(
    application_form_response: dict[str, Any],
    *,
    eeoc_data: dict[str, Any] | None = None,
    referral_id: str | None = None,
    custom_questionnaire_responses: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Wrap the form response in the careers UI apply POST body."""
    return {
        "applicationFormResponse": application_form_response,
        "eeocData": eeoc_data,
        "referralId": referral_id,
        "customQuestionnaireResponses": custom_questionnaire_responses or [],
    }


def extract_application_id(response: object) -> str | None:
    """Best-effort application id from a successful apply response."""
    if not isinstance(response, dict):
        return None
    for key in ("applicationId", "application_id", "id", "uuid"):
        value = response.get(key)
        if isinstance(value, str | int) and str(value).strip():
            return str(value).strip()
    data = response.get("data")
    if isinstance(data, dict):
        return extract_application_id(data)
    return None


def extract_error_message(response: object) -> str:
    """Human-readable error from a Rippling JSON error body."""
    if isinstance(response, dict):
        for key in ("message", "error", "detail"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if response.get("error") == "turnstile_verification_failure":
            return "turnstile_verification_failure"
    return "rippling apply failed"


def _current_company(profile: ProfileData, config: dict[str, Any], company: str) -> str:
    for key in ("current_company", "company"):
        raw = config.get(key) or profile.answers.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    for entry in profile.work_experience:
        if entry.is_current and entry.company.strip():
            return entry.company.strip()
    for entry in profile.work_experience:
        if entry.company.strip():
            return entry.company.strip()
    return company.strip()


def _location(profile: ProfileData, config: dict[str, Any]) -> str:
    raw = config.get("location") or profile.location
    text = str(raw or "").strip()
    # Rippling's default label is "Location (city only)" — keep the first segment.
    if "," in text:
        return text.split(",", 1)[0].strip()
    return text


def _ensure_http(url: str) -> str:
    cleaned = url.strip()
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    return f"https://{cleaned}"
