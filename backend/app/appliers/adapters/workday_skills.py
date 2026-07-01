"""Workday CXS skills and languages helpers for the apply adapter."""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.workday_common import (
    WorkdayTarget,
    cxs_jobapplication_url,
    request_headers,
)
from app.appliers.adapters.workday_experience import SectionSubmitResult
from app.schemas.profile import LanguageEntry, ProfileData
from app.scrapers.http import HttpClient


def applicable_skills(profile: ProfileData) -> list[str]:
    """Profile skill names with non-empty text."""
    return [skill.strip() for skill in profile.skills if skill.strip()]


def applicable_languages(profile: ProfileData) -> list[LanguageEntry]:
    """Profile language rows with the minimum fields Workday needs."""
    return [entry for entry in profile.languages if entry.language.strip()]


def build_skill_body(skill_name: str) -> dict[str, Any]:
    """Map a profile skill name to the Workday CXS create payload."""
    return {"skill": {"descriptor": skill_name.strip()}}


def build_language_body(entry: LanguageEntry) -> dict[str, Any]:
    """Map a profile language row to the Workday CXS create payload."""
    body: dict[str, Any] = {"language": {"descriptor": entry.language.strip()}}
    if entry.is_native:
        body["native"] = True
    proficiency = entry.proficiency.strip()
    if proficiency:
        body["languageProficiency"] = {"descriptor": proficiency}
    return body


def preview_skills(profile: ProfileData) -> list[dict[str, Any]]:
    """Dry-run payloads for configured skills."""
    return [build_skill_body(skill) for skill in applicable_skills(profile)]


def preview_languages(profile: ProfileData) -> list[dict[str, Any]]:
    """Dry-run payloads for configured language rows."""
    return [build_language_body(entry) for entry in applicable_languages(profile)]


def submit_skills(
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
    """POST each configured skill before questionnaires/finalize."""
    if config.get("skip_skills"):
        return []

    url = cxs_jobapplication_url(target, application_id, "skills")
    headers = request_headers(
        target,
        job_path,
        csrf_token=csrf_token,
        session_id=session_id,
        credentials=credentials,
    )
    results: list[SectionSubmitResult] = []
    for index, skill in enumerate(applicable_skills(profile)):
        payload = build_skill_body(skill)
        try:
            response = http.post_json(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            results.append(
                SectionSubmitResult(
                    section="skills",
                    index=index,
                    payload=payload,
                    error=str(exc),
                )
            )
            return results
        error = _response_error(response)
        results.append(
            SectionSubmitResult(
                section="skills",
                index=index,
                payload=payload,
                response=response if isinstance(response, dict) else None,
                error=error,
            )
        )
        if error:
            return results
    return results


def submit_languages(
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
    """POST each configured language row before questionnaires/finalize."""
    if config.get("skip_languages"):
        return []

    url = cxs_jobapplication_url(target, application_id, "languages")
    headers = request_headers(
        target,
        job_path,
        csrf_token=csrf_token,
        session_id=session_id,
        credentials=credentials,
    )
    results: list[SectionSubmitResult] = []
    for index, entry in enumerate(applicable_languages(profile)):
        payload = build_language_body(entry)
        try:
            response = http.post_json(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            results.append(
                SectionSubmitResult(
                    section="languages",
                    index=index,
                    payload=payload,
                    error=str(exc),
                )
            )
            return results
        error = _response_error(response)
        results.append(
            SectionSubmitResult(
                section="languages",
                index=index,
                payload=payload,
                response=response if isinstance(response, dict) else None,
                error=error,
            )
        )
        if error:
            return results
    return results


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
