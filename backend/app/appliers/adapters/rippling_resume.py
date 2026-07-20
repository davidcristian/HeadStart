"""Resume / cover-letter upload for Rippling public board apply."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.appliers.adapters.rippling_common import file_upload_url
from app.schemas.profile import ResumeFile
from app.scrapers.http import HttpClient


def upload_application_file(
    http: HttpClient,
    *,
    board: str,
    resume_file: ResumeFile | None = None,
    content: bytes | None = None,
    filename: str | None = None,
    content_type: str | None = None,
) -> tuple[str, str]:
    """Upload a file via Rippling's presigned S3 POST; return (url, content_type)."""
    data, name, ctype = _resolve_bytes(
        resume_file=resume_file,
        content=content,
        filename=filename,
        content_type=content_type,
    )
    upload = http.get_json(
        file_upload_url(),
        params={"jobBoardSlug": board, "contentType": ctype},
    )
    payload = _upload_payload(upload)
    fields = {str(key): str(value) for key, value in payload["fields"].items()}
    # Only send acl when the presign response asks for it (false/null → omit).
    acl = payload.get("acl")
    form_fields = dict(fields)
    if acl:
        form_fields["acl"] = str(acl)

    try:
        http.post_multipart(
            payload["s3_url"],
            data=form_fields,
            files={"file": (name, data, ctype)},
        )
    except httpx.HTTPError as exc:
        raise ValueError(f"rippling resume upload to S3 failed: {exc}") from exc

    return _final_resume_url(payload, fields), ctype


def _resolve_bytes(
    *,
    resume_file: ResumeFile | None,
    content: bytes | None,
    filename: str | None,
    content_type: str | None,
) -> tuple[bytes, str, str]:
    if resume_file is not None:
        return (
            resume_file.data,
            resume_file.filename or "resume.pdf",
            resume_file.content_type.strip() or "application/pdf",
        )
    if content is None:
        raise ValueError("rippling file upload needs resume_file or content bytes")
    return (
        content,
        filename or "upload.bin",
        (content_type or "application/octet-stream").strip(),
    )


def _upload_payload(upload: object) -> dict[str, Any]:
    if not isinstance(upload, dict):
        raise ValueError("rippling file_upload_url returned unexpected payload")
    data = upload.get("data")
    if not isinstance(data, dict):
        raise ValueError("rippling file_upload_url missing data object")
    s3_url = str(data.get("url") or "").strip()
    fields = data.get("fields")
    final = data.get("finalUrl")
    if not s3_url or not isinstance(fields, dict) or not isinstance(final, dict):
        raise ValueError("rippling file_upload_url missing url/fields/finalUrl")
    final_url = str(final.get("url") or "").strip()
    if not final_url:
        raise ValueError("rippling file_upload_url missing finalUrl.url")
    return {
        "s3_url": s3_url,
        "fields": fields,
        "final_url": final_url,
        "acl": data.get("acl"),
    }


def _final_resume_url(payload: dict[str, Any], fields: dict[str, str]) -> str:
    """Attach uploadsig when the careers UI would (required by apply validation)."""
    url = str(payload["final_url"])
    sig = fields.get("uploadsig")
    if not sig:
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if "uploadsig" not in query:
        query["uploadsig"] = sig
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
