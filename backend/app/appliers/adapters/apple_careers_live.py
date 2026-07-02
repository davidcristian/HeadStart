"""Apple Careers live-submit HTTP helpers."""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.apple_careers_common import (
    apply_job_url,
    apply_page_url,
    questionnaire_url,
    request_headers,
    unwrap_response,
    upload_resume_url,
)
from app.appliers.adapters.apple_careers_detail import AppleCareersJobDetail
from app.appliers.adapters.apple_careers_payload import build_resume_ref
from app.appliers.types import ApplyContext
from app.schemas.profile import ResumeFile
from app.scrapers.http import HttpClient


def fetch_questionnaire(
    http: HttpClient,
    detail: AppleCareersJobDetail,
    csrf_token: str,
    ctx: ApplyContext,
) -> dict[str, Any] | None:
    """Load application questionnaire metadata when the session can access it."""
    headers = request_headers(
        csrf_token=csrf_token,
        referer=apply_page_url(detail.locale, detail.position_id),
        credentials=ctx.credentials,
    )
    try:
        response = http.get_json(questionnaire_url(detail.position_id), headers=headers)
    except httpx.HTTPError:
        return None
    data = unwrap_response(response)
    return data if isinstance(data, dict) else None


def questionnaire_answers(
    questionnaire: dict[str, Any] | None,
    profile_answers: dict[str, str],
) -> dict[str, Any] | None:
    """Map profile.answers onto a questionnaire payload when ids are known."""
    if not questionnaire or not profile_answers:
        return None
    questionnaire_id = questionnaire.get("id") or questionnaire.get("questionnaireId")
    if not questionnaire_id:
        return None
    mapped = {key: value for key, value in profile_answers.items() if value}
    if not mapped:
        return None
    return {
        "id": questionnaire_id,
        "questionnaireId": questionnaire_id,
        "questionCategory": "APPLICATION",
        "answers": mapped,
        "reset": False,
    }


def upload_resume(
    http: HttpClient,
    talent_id: str,
    resume_file: ResumeFile,
    *,
    csrf_token: str,
    ctx: ApplyContext,
    detail: AppleCareersJobDetail,
) -> dict[str, Any]:
    """Upload a resume file and return the roles.resume reference object."""
    headers = request_headers(
        csrf_token=csrf_token,
        referer=apply_page_url(detail.locale, detail.position_id),
        credentials=ctx.credentials,
        json_body=False,
    )
    headers.pop("Content-Type", None)
    upload_url = (
        f"{upload_resume_url(talent_id)}"
        f"?talentId={talent_id}&categoryId=resume&isParsingRequired=true"
    )
    response = http.post_multipart(
        upload_url,
        data={},
        files={
            "file": (
                resume_file.filename,
                resume_file.data,
                resume_file.content_type,
            )
        },
        headers=headers,
    )
    data = unwrap_response(response)
    resume_ref = build_resume_ref(data if isinstance(data, dict) else None)
    if resume_ref is None:
        raise ValueError("apple_careers resume upload did not return a file id")
    return resume_ref


def submit_apply_job(
    http: HttpClient,
    talent_id: str,
    body: dict[str, Any],
    *,
    csrf_token: str,
    ctx: ApplyContext,
    detail: AppleCareersJobDetail,
) -> Any:
    """PUT the final applyJob payload."""
    headers = request_headers(
        csrf_token=csrf_token,
        referer=apply_page_url(detail.locale, detail.position_id),
        credentials=ctx.credentials,
    )
    return http.put_json(apply_job_url(talent_id), json=body, headers=headers)
