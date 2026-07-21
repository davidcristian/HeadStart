"""Resume upload for Workable public careers apply."""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.workable_common import resume_upload_url
from app.schemas.profile import ResumeFile
from app.scrapers.http import HttpClient


def upload_resume(
    http: HttpClient,
    *,
    shortcode: str,
    resume_file: ResumeFile,
) -> str:
    """Upload a resume via Workable's presigned S3 POST; return the download URL."""
    name = resume_file.filename or "resume.pdf"
    ctype = resume_file.content_type.strip() or "application/pdf"
    try:
        upload = http.get_json(
            resume_upload_url(shortcode),
            params={"contentType": ctype},
        )
    except httpx.HTTPError as exc:
        raise ValueError(f"workable resume presign failed: {exc}") from exc

    payload = _upload_payload(upload)
    form_fields = {str(key): str(value) for key, value in payload["fields"].items()}
    # Policy requires Content-Type to be present (starts-with "").
    form_fields.setdefault("Content-Type", ctype)

    try:
        http.post_multipart(
            payload["s3_url"],
            data=form_fields,
            files={"file": (name, resume_file.data, ctype)},
        )
    except httpx.HTTPError as exc:
        raise ValueError(f"workable resume upload to S3 failed: {exc}") from exc

    return payload["download_url"]


def _upload_payload(upload: object) -> dict[str, Any]:
    if not isinstance(upload, dict):
        raise ValueError("workable form/upload/resume returned unexpected payload")
    post = upload.get("uploadPostUrl")
    if not isinstance(post, dict):
        raise ValueError("workable form/upload/resume missing uploadPostUrl")
    s3_url = str(post.get("url") or "").strip()
    fields = post.get("fields")
    download = str(upload.get("downloadUrl") or "").strip()
    if not s3_url or not isinstance(fields, dict) or not download:
        raise ValueError("workable form/upload/resume missing url/fields/downloadUrl")
    return {"s3_url": s3_url, "fields": fields, "download_url": download}
