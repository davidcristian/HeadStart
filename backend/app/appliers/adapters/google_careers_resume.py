"""Google Careers resume attachment upload (Scotty resumable protocol)."""

from __future__ import annotations

import base64
import binascii
import hashlib
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from app.schemas.profile import ResumeFile
from app.scrapers.http import HttpClient

DEFAULT_UPLOAD_URL = "https://www.google.com/about/careers/attachmentupload/upload"
_MAX_RESUME_BYTES = 2_097_152
_GOOGLE_ORIGIN = "https://www.google.com"


@dataclass(frozen=True, slots=True)
class GoogleCareersResumeAttachment:
    """Resume attachment reference returned by Google's upload endpoint."""

    attachment_id: str
    filename: str


def build_upload_headers(
    resume_file: ResumeFile,
    *,
    parse_resume: bool = False,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Headers for the Scotty resumable upload start command."""
    headers = {
        "Content-Length": str(resume_file.size_bytes),
        "Content-Type": resume_file.content_type or "application/octet-stream",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-File-Name": quote(resume_file.filename),
        "X-Goog-Upload-Protocol": "resumable",
        "parseResume": "true" if parse_resume else "false",
        "Origin": _GOOGLE_ORIGIN,
        "Referer": f"{_GOOGLE_ORIGIN}/about/careers/applications/profile",
    }
    if extra:
        headers.update(extra)
    return headers


def build_finalize_headers(*, offset: int = 0) -> dict[str, str]:
    """Headers for the Scotty upload finalize command."""
    return {
        "X-Goog-Upload-Command": "upload, finalize",
        "X-Goog-Upload-Offset": str(offset),
        "Origin": _GOOGLE_ORIGIN,
        "Referer": f"{_GOOGLE_ORIGIN}/about/careers/applications/profile",
    }


def sapisidhash_headers(cookies: dict[str, str]) -> dict[str, str]:
    """Build Google's SAPISIDHASH Authorization header when SAPISID is present."""
    token = (
        cookies.get("SAPISID")
        or cookies.get("__Secure-1PAPISID")
        or cookies.get("__Secure-3PAPISID")
    )
    if not token:
        return {}
    timestamp = int(time.time())
    digest = hashlib.sha1(f"{timestamp} {token} {_GOOGLE_ORIGIN}".encode()).hexdigest()
    return {"Authorization": f"SAPISIDHASH {timestamp}_{digest}"}


def resume_attachment_for_payload(
    attachment: GoogleCareersResumeAttachment,
) -> dict[str, str]:
    """Map an upload result into the Careers profile JSON envelope."""
    return {
        "id": attachment.attachment_id,
        "name": attachment.filename,
    }


def preview_resume_upload(resume_file: ResumeFile | None) -> dict[str, Any] | None:
    """Dry-run metadata for a pending Scotty resume upload."""
    if resume_file is None:
        return None
    return {
        "upload_url": DEFAULT_UPLOAD_URL,
        "filename": resume_file.filename,
        "content_type": resume_file.content_type,
        "size_bytes": resume_file.size_bytes,
        "parse_resume": False,
    }


def upload_resume_attachment(
    http: HttpClient,
    resume_file: ResumeFile,
    *,
    upload_url: str = DEFAULT_UPLOAD_URL,
    credentials: dict[str, dict[str, str]] | None = None,
    parse_resume: bool = False,
) -> GoogleCareersResumeAttachment:
    """Upload a resume file via Google's Scotty resumable protocol."""
    if resume_file.size_bytes <= 0:
        raise ValueError("google_careers resume upload requires non-empty file bytes")
    if resume_file.size_bytes > _MAX_RESUME_BYTES:
        raise ValueError("google_careers resume file exceeds the 2 MB limit")

    cookies = (credentials or {}).get("cookies") or {}
    auth_headers = sapisidhash_headers(cookies)
    start_headers = build_upload_headers(resume_file, parse_resume=parse_resume, extra=auth_headers)

    start_resp = http.post_raw(upload_url, content=b"", headers=start_headers)
    session_url = start_resp.headers.get("X-Goog-Upload-URL") or start_resp.headers.get(
        "x-goog-upload-url"
    )
    if not session_url:
        raise ValueError("google_careers resume upload start did not return X-Goog-Upload-URL")

    finalize_headers = {**auth_headers, **build_finalize_headers(offset=0)}
    finalize_resp = http.post_raw(
        session_url,
        content=resume_file.data,
        headers=finalize_headers,
    )
    attachment = parse_upload_response(finalize_resp.text)
    if attachment.filename == "resume":
        attachment = GoogleCareersResumeAttachment(
            attachment_id=attachment.attachment_id,
            filename=resume_file.filename,
        )
    return attachment


def parse_upload_response(body: str) -> GoogleCareersResumeAttachment:
    """Parse the base64-encoded protobuf returned after Scotty finalize."""
    raw = _decode_response_body(body)
    attachment_id, filename = _extract_resume_attachment_fields(raw)
    if not attachment_id:
        raise ValueError("google_careers resume upload response did not include an attachment id")
    return GoogleCareersResumeAttachment(
        attachment_id=attachment_id,
        filename=filename or "resume",
    )


def _decode_response_body(body: str) -> bytes:
    cleaned = body.strip()
    if not cleaned:
        raise ValueError("google_careers resume upload returned an empty body")
    try:
        return base64.b64decode(cleaned, validate=True)
    except (ValueError, binascii.Error):
        return cleaned.encode("utf-8")


def _extract_resume_attachment_fields(payload: bytes) -> tuple[str, str]:
    """Best-effort parse of field 1 (attachment message) from the upload protobuf."""
    attachment_message = _first_length_delimited(payload, field_number=1)
    if attachment_message is None:
        return "", ""
    attachment_id = _first_string(attachment_message, field_number=1) or ""
    filename = _first_string(attachment_message, field_number=2) or ""
    return attachment_id, filename


def _first_length_delimited(payload: bytes, *, field_number: int) -> bytes | None:
    index = 0
    expected_tag = (field_number << 3) | 2
    while index < len(payload):
        tag, index = _read_varint(payload, index)
        if tag == expected_tag:
            length, index = _read_varint(payload, index)
            end = index + length
            return payload[index:end]
        wire_type = tag & 0x07
        index = _skip_field(payload, index, wire_type)
    return None


def _first_string(payload: bytes, *, field_number: int) -> str | None:
    chunk = _first_length_delimited(payload, field_number=field_number)
    if chunk is None:
        return None
    try:
        return chunk.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _read_varint(payload: bytes, index: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while index < len(payload):
        byte = payload[index]
        index += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, index
        shift += 7
        if shift > 63:
            break
    raise ValueError("google_careers resume upload response contained a truncated varint")


def _skip_field(payload: bytes, index: int, wire_type: int) -> int:
    if wire_type == 0:
        _, index = _read_varint(payload, index)
        return index
    if wire_type == 1:
        return index + 8
    if wire_type == 2:
        length, index = _read_varint(payload, index)
        return index + length
    if wire_type == 5:
        return index + 4
    raise ValueError("google_careers resume upload response used an unsupported wire type")
