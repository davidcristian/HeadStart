"""Shared helpers for resume file attachments in apply adapters."""

from __future__ import annotations

import base64
from typing import Any

from app.schemas.profile import ResumeFile, ResumeFileMeta


def resume_meta_for_payload(resume_file: ResumeFile | None) -> dict[str, Any] | None:
    """Resume metadata safe to include in dry-run payloads (no file bytes)."""
    if resume_file is None:
        return None
    return ResumeFileMeta(
        filename=resume_file.filename,
        content_type=resume_file.content_type,
        size_bytes=resume_file.size_bytes,
    ).model_dump()


def indeed_resume_file_fields(resume_file: ResumeFile) -> dict[str, str]:
    """Indeed Apply resume.file object for live smartapply submit."""
    content_type = resume_file.content_type.strip() or "application/octet-stream"
    return {
        "fileName": resume_file.filename,
        "contentType": content_type,
        "data": base64.b64encode(resume_file.data).decode("ascii"),
    }


def greenhouse_resume_fields(resume_file: ResumeFile | None) -> dict[str, str]:
    """Greenhouse JSON fields for a direct resume upload."""
    if resume_file is None:
        return {}
    return {
        "resume_content": base64.b64encode(resume_file.data).decode("ascii"),
        "resume_content_filename": resume_file.filename,
    }


def workday_content_type(content_type: str) -> dict[str, str]:
    """Workday CXS content type reference for attachment metadata."""
    normalized = content_type.strip() or "application/octet-stream"
    descriptor = normalized.rsplit("/", 1)[-1]
    return {
        "id": f"Content_Type_ID={normalized}",
        "descriptor": descriptor,
    }


def lever_resume_part(resume_file: ResumeFile | None) -> tuple[str, tuple[str, bytes, str]] | None:
    """Multipart file tuple for Lever's `resume` field."""
    if resume_file is None:
        return None
    return ("resume", (resume_file.filename, resume_file.data, resume_file.content_type))


def flatten_lever_form_fields(payload: dict[str, Any]) -> dict[str, str]:
    """Flatten Lever JSON payload keys into multipart form field names."""
    import json

    parts: dict[str, str] = {}
    for key, value in payload.items():
        if key == "urls" and isinstance(value, dict):
            for label, url in value.items():
                parts[f"urls[{label}]"] = str(url)
        elif key == "consent" and isinstance(value, dict):
            parts["consent"] = json.dumps(value)
        elif isinstance(value, bool):
            parts[key] = "true" if value else "false"
        else:
            parts[key] = str(value)
    return parts
