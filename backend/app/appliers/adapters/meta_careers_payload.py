"""Meta Careers application payload builders."""

from __future__ import annotations

from typing import Any

from app.appliers.adapters.meta_careers_common import apply_url, public_job_url
from app.appliers.adapters.meta_careers_detail import MetaCareersJobDetail
from app.appliers.resume import resume_meta_for_payload
from app.appliers.text import render_cover_letter, split_name
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile


def build_application_state(
    detail: MetaCareersJobDetail,
    profile: ProfileData | ApplyProfile,
    *,
    company: str,
    job_title: str,
    cover_letter: str | None = None,
    resume_file: ResumeFile | None = None,
) -> dict[str, Any]:
    """Map application profile fields to Meta's create-application form state."""
    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name:
        raise ValueError("profile full_name is required to apply on Meta Careers")
    if not email:
        raise ValueError("profile email is required to apply on Meta Careers")

    full_name = profile.full_name.strip()
    work = list(profile.work_experience)
    education = list(profile.education)
    skills = [skill.strip() for skill in profile.skills if skill.strip()]

    state: dict[str, Any] = {
        "requisition_id": detail.requisition_id,
        "candidateName": full_name,
        "candidateFirstName": first_name,
        "candidateLastName": last_name or first_name,
        "candidatePhone": profile.phone.strip() or None,
        "candidateEmail": email,
        "candidateLocationID": profile.answers.get("candidate_location_id"),
        "urls": _profile_urls(profile),
        "collegeSchoolNames": [entry.school for entry in education if entry.school.strip()],
        "collegeDegreeNames": [entry.degree for entry in education if entry.degree.strip()],
        "collegeConcentration1Names": [
            entry.field_of_study for entry in education if entry.field_of_study.strip()
        ],
        "collegeConcentration2Names": [],
        "highSchoolName": profile.answers.get("high_school_name"),
        "candidateSkills": skills,
        "noWorkExperience": not work,
        "workEligibleUS": _yes_no_answer(profile.answers, "work_authorization", "work_eligible_us"),
        "requiresSponsorship": _yes_no_answer(
            profile.answers, "requires_sponsorship", "visa_sponsorship"
        ),
        "workEmployerNames": [entry.company for entry in work if entry.company.strip()],
        "workPositionNames": [entry.job_title for entry in work if entry.job_title.strip()],
        "workLocationNames": [entry.location for entry in work if entry.location.strip()],
        "workEmployerFBIDs": [],
        "workPositionFBIDs": [],
        "workLocationFBIDs": [],
        "workIsCurrent": [entry.is_current for entry in work],
        "workStartMonths": [_month(entry.start_month) for entry in work],
        "workStartYears": [_year(entry.start_year) for entry in work],
        "workEndMonths": [_month(entry.end_month) for entry in work],
        "workEndYears": [_year(entry.end_year) for entry in work],
        "workDescriptions": [entry.description for entry in work],
        "candidateResumeFileName": resume_file.filename if resume_file is not None else None,
        "candidateGender": profile.answers.get("gender"),
        "candidateRaceEthnicities": profile.answers.get("race_ethnicity"),
        "veteranStatus": profile.answers.get("veteran_status"),
        "disabilityStatus": profile.answers.get("disability_status"),
        "coverLetter": _cover_letter_text(
            profile,
            company=company,
            job_title=job_title,
            cover_letter=cover_letter,
        ),
    }
    return _drop_empty(state)


def build_submit_input(
    application_state: dict[str, Any],
    *,
    session_id: str,
    resume_file: ResumeFile | None = None,
    classic_view: bool = False,
    is_ra: bool = True,
) -> dict[str, Any]:
    """Wrap application state in Meta's xcp_create_application_v2 mutation input."""
    return {
        "session_id": session_id,
        "classic_view": classic_view,
        "is_ra": is_ra,
        "application": application_state,
        "candidateResumeFile": "candidateResumeFile" if resume_file is not None else None,
        "attachment0File": None,
        "attachment1File": None,
        "attachment2File": None,
        "attachment3File": None,
        "attachment4File": None,
    }


def build_application_payload(
    detail: MetaCareersJobDetail,
    profile: ProfileData | ApplyProfile,
    *,
    company: str,
    job_title: str,
    cover_letter: str | None = None,
    resume_file: ResumeFile | None = None,
    session_id: str | None = None,
    include_submit_input: bool = False,
) -> dict[str, Any]:
    """Dry-run preview payload for Meta Careers applications."""
    application_state = build_application_state(
        detail,
        profile,
        company=company,
        job_title=job_title,
        cover_letter=cover_letter,
        resume_file=resume_file,
    )
    payload: dict[str, Any] = {
        "requisition_id": detail.requisition_id,
        "title": detail.title,
        "locations": list(detail.locations),
        "departments": list(detail.departments),
        "job_url": public_job_url(detail.requisition_id),
        "apply_url": apply_url(detail.requisition_id),
        "application": application_state,
        "graphql": {
            "job_details_query": "CandidatePortalJobDetailsViewQuery",
            "submit_mutation": "CandidateChatbotApplicationDetailSubmitMutation",
        },
    }
    resume_meta = resume_meta_for_payload(resume_file)
    if resume_meta is not None:
        payload["resume_file"] = resume_meta
    if include_submit_input and session_id:
        payload["submit_input"] = build_submit_input(
            application_state,
            session_id=session_id,
            resume_file=resume_file,
        )
    return payload


def _cover_letter_text(
    profile: ProfileData | ApplyProfile,
    *,
    company: str,
    job_title: str,
    cover_letter: str | None,
) -> str | None:
    if cover_letter and cover_letter.strip():
        return cover_letter.strip()
    template = profile.cover_letter_template.strip()
    if not template:
        return None
    return render_cover_letter(template, company=company, job_title=job_title)


def _profile_urls(profile: ProfileData | ApplyProfile) -> list[str] | None:
    urls = [
        profile.links.website.strip(),
        profile.links.linkedin.strip(),
        profile.links.github.strip(),
    ]
    cleaned = [url for url in urls if url]
    return cleaned or None


def _yes_no_answer(answers: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = answers.get(key)
        if not value:
            continue
        normalized = value.strip().lower()
        if normalized in {"yes", "y", "true", "1"}:
            return "0"
        if normalized in {"no", "n", "false", "0"}:
            return "1"
    return None


def _month(value: int | None) -> str | None:
    return str(value) if value is not None else None


def _year(value: int | None) -> str | None:
    return str(value) if value is not None else None


def _drop_empty(state: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in state.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, list) and not value:
            continue
        cleaned[key] = value
    return cleaned
