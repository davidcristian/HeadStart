"""Workday CXS work-experience and education helpers for the apply adapter."""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.workday_common import (
    WorkdayTarget,
    cxs_jobapplication_url,
    request_headers,
)
from app.schemas.profile import EducationEntry, ProfileData, WorkExperienceEntry
from app.scrapers.http import HttpClient


class SectionSubmitResult:
    """Outcome of submitting one work-experience or education row."""

    def __init__(
        self,
        *,
        section: str,
        index: int,
        payload: dict[str, Any],
        response: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.section = section
        self.index = index
        self.payload = payload
        self.response = response
        self.error = error

    @property
    def ok(self) -> bool:
        return self.error is None


def applicable_work_experience(profile: ProfileData) -> list[WorkExperienceEntry]:
    """Profile rows with the minimum fields Workday needs to create an entry."""
    return [
        entry
        for entry in profile.work_experience
        if (
            entry.job_title.strip()
            and entry.company.strip()
            and entry.start_year
            and entry.start_month
        )
    ]


def applicable_education(profile: ProfileData) -> list[EducationEntry]:
    """Profile rows with the minimum fields Workday needs to create an entry."""
    return [entry for entry in profile.education if entry.school.strip()]


def build_work_experience_body(entry: WorkExperienceEntry) -> dict[str, Any]:
    """Map a profile work-experience row to the Workday CXS create payload."""
    body: dict[str, Any] = {
        "jobTitle": entry.job_title.strip(),
        "companyName": entry.company.strip(),
        "currentlyWorkHere": entry.is_current,
        "startDate": f"{entry.start_year}-{entry.start_month:02d}-01",
    }
    location = entry.location.strip()
    if location:
        body["location"] = location
    description = entry.description.strip()
    if description:
        body["roleDescription"] = description
    if not entry.is_current and entry.end_year and entry.end_month:
        body["endDate"] = f"{entry.end_year}-{entry.end_month:02d}-01"
    return body


def build_education_body(entry: EducationEntry) -> dict[str, Any]:
    """Map a profile education row to the Workday CXS create payload."""
    body: dict[str, Any] = {"schoolName": entry.school.strip()}
    degree = entry.degree.strip()
    if degree:
        body["degree"] = {"descriptor": degree}
    field = entry.field_of_study.strip()
    if field:
        body["fieldOfStudy"] = {"descriptor": field}
    if entry.start_year:
        body["firstYearAttended"] = f"{entry.start_year}-01-01"
    if entry.end_year:
        body["lastYearAttended"] = f"{entry.end_year}-01-01"
    gpa = entry.gpa.strip()
    if gpa:
        body["gradeAverage"] = gpa
    return body


def preview_work_experiences(profile: ProfileData) -> list[dict[str, Any]]:
    """Dry-run payloads for configured work-experience rows."""
    return [build_work_experience_body(entry) for entry in applicable_work_experience(profile)]


def preview_educations(profile: ProfileData) -> list[dict[str, Any]]:
    """Dry-run payloads for configured education rows."""
    return [build_education_body(entry) for entry in applicable_education(profile)]


def submit_work_experiences(
    http: HttpClient,
    *,
    target: WorkdayTarget,
    application_id: str,
    profile: ProfileData,
    job_path: str,
    config: dict[str, Any],
    csrf_token: str,
    session_id: str,
    credentials: dict[str, dict[str, str]] | None,
) -> list[SectionSubmitResult]:
    """POST each configured work-experience row before questionnaires/finalize."""
    if config.get("skip_work_experience"):
        return []

    url = cxs_jobapplication_url(target, application_id, "workexperiences")
    headers = request_headers(
        target,
        job_path,
        csrf_token=csrf_token,
        session_id=session_id,
        credentials=credentials,
    )
    results: list[SectionSubmitResult] = []
    for index, entry in enumerate(applicable_work_experience(profile)):
        payload = build_work_experience_body(entry)
        try:
            response = http.post_json(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            results.append(
                SectionSubmitResult(
                    section="workexperiences",
                    index=index,
                    payload=payload,
                    error=str(exc),
                )
            )
            return results
        error = _response_error(response)
        results.append(
            SectionSubmitResult(
                section="workexperiences",
                index=index,
                payload=payload,
                response=response if isinstance(response, dict) else None,
                error=error,
            )
        )
        if error:
            return results
    return results


def submit_educations(
    http: HttpClient,
    *,
    target: WorkdayTarget,
    application_id: str,
    profile: ProfileData,
    job_path: str,
    config: dict[str, Any],
    csrf_token: str,
    session_id: str,
    credentials: dict[str, dict[str, str]] | None,
) -> list[SectionSubmitResult]:
    """POST each configured education row before questionnaires/finalize."""
    if config.get("skip_education"):
        return []

    url = cxs_jobapplication_url(target, application_id, "educations")
    headers = request_headers(
        target,
        job_path,
        csrf_token=csrf_token,
        session_id=session_id,
        credentials=credentials,
    )
    results: list[SectionSubmitResult] = []
    for index, entry in enumerate(applicable_education(profile)):
        payload = build_education_body(entry)
        try:
            response = http.post_json(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            results.append(
                SectionSubmitResult(
                    section="educations",
                    index=index,
                    payload=payload,
                    error=str(exc),
                )
            )
            return results
        error = _response_error(response)
        results.append(
            SectionSubmitResult(
                section="educations",
                index=index,
                payload=payload,
                response=response if isinstance(response, dict) else None,
                error=error,
            )
        )
        if error:
            return results
    return results


def sections_payload(results: list[SectionSubmitResult]) -> dict[str, Any]:
    """Serialize section submit results for apply previews and audit payloads."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        grouped.setdefault(result.section, []).append(
            {
                "payload": result.payload,
                **({"responseId": result.response.get("id")} if result.response else {}),
                **({"error": result.error} if result.error else {}),
            }
        )
    return grouped


def _response_error(response: object) -> str | None:
    if not isinstance(response, dict):
        return None
    if response.get("errorCode"):
        message = response.get("message") or response.get("errorCode")
        return str(message)
    if isinstance(response.get("errors"), list) and response["errors"]:
        first = response["errors"][0]
        if isinstance(first, dict):
            return str(first.get("error") or first.get("code") or first)
    return None
