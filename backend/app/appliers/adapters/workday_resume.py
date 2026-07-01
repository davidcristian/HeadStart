"""Workday CXS resume upload helpers for the apply adapter."""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.workday_common import (
    WorkdayTarget,
    cxs_jobapplication_url,
    request_headers,
)
from app.appliers.resume import resume_meta_for_payload, workday_content_type
from app.schemas.profile import ResumeFile
from app.scrapers.http import HttpClient

_ATTACHMENTS_FIELD = "body"


def attachments_url(target: WorkdayTarget) -> str:
    """CXS common attachments endpoint used before resumeattachments."""
    return f"{target.api_base()}/attachments"


def build_resume_attachment_payload(
    resume_file: ResumeFile,
    *,
    uploaded_file_id: str,
    content_type: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Shape expected by POST jobapplication/{id}/resumeattachments."""
    resolved = content_type or workday_content_type(resume_file.content_type)
    return {
        "attachments": [
            {
                "file": uploaded_file_id,
                "fileName": resume_file.filename,
                "fileLength": resume_file.size_bytes,
                "contentType": resolved,
            }
        ]
    }


def preview_resume_attachment(
    resume_file: ResumeFile | None,
) -> dict[str, Any] | None:
    """Dry-run resume metadata without uploading bytes."""
    if resume_file is None:
        return None
    meta = resume_meta_for_payload(resume_file)
    if meta is None:
        return None
    return {
        "attachments": [
            {
                "fileName": meta["filename"],
                "fileLength": meta["size_bytes"],
                "contentType": workday_content_type(resume_file.content_type),
            }
        ]
    }


def upload_resume_attachment(
    http: HttpClient,
    *,
    target: WorkdayTarget,
    application_id: str,
    resume_file: ResumeFile,
    job_path: str,
    csrf_token: str,
    session_id: str,
    credentials: dict[str, dict[str, str]] | None,
) -> dict[str, Any]:
    """Upload the resume file and register it on the application."""
    upload_headers = request_headers(
        target,
        job_path,
        csrf_token=csrf_token,
        session_id=session_id,
        credentials=credentials,
        multipart=True,
    )
    upload_response = http.post_multipart(
        attachments_url(target),
        data={},
        files={
            _ATTACHMENTS_FIELD: (
                resume_file.filename,
                resume_file.data,
                resume_file.content_type,
            )
        },
        headers=upload_headers,
    )
    if not isinstance(upload_response, dict):
        raise ValueError("workday attachments upload returned an unexpected response")
    if upload_response.get("errorCode"):
        message = upload_response.get("message") or upload_response.get("errorCode")
        raise ValueError(str(message))

    file_id = upload_response.get("id")
    if not file_id:
        raise ValueError("workday attachments upload did not return a file id")

    content_type = upload_response.get("contentType")
    if not isinstance(content_type, dict):
        content_type = workday_content_type(resume_file.content_type)

    payload = build_resume_attachment_payload(
        resume_file,
        uploaded_file_id=str(file_id),
        content_type=content_type,
    )
    submit_url = cxs_jobapplication_url(target, application_id, "resumeattachments")
    submit_headers = request_headers(
        target,
        job_path,
        csrf_token=csrf_token,
        session_id=session_id,
        credentials=credentials,
    )
    try:
        submitted = http.post_json(submit_url, json=payload, headers=submit_headers)
    except httpx.HTTPError as exc:
        raise ValueError(str(exc)) from exc

    if isinstance(submitted, list):
        raise ValueError("workday resumeattachments rejected the upload")
    if isinstance(submitted, dict) and submitted.get("errorCode"):
        message = submitted.get("message") or submitted.get("errorCode")
        raise ValueError(str(message))

    return {
        "upload": upload_response,
        "resumeAttachments": payload,
        "response": submitted if isinstance(submitted, dict) else None,
    }
