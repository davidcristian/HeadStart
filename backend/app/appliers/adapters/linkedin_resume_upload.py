"""LinkedIn Easy Apply resume upload via Voyager media metadata + Ambry."""

from __future__ import annotations

from typing import Any

from app.appliers.adapters.linkedin_common import (
    voyager_request_cookies,
    voyager_request_headers,
)
from app.schemas.profile import ResumeFile
from app.scrapers.http import HttpClient

MEDIA_UPLOAD_URL = "https://www.linkedin.com/voyager/api/voyagerMediaUploadMetadata?action=upload"


def upload_easy_apply_resume(
    http: HttpClient,
    resume_file: ResumeFile,
    credentials: dict[str, dict[str, str]] | None,
) -> str:
    """Upload a resume file and return the digital media asset URN."""
    headers = voyager_request_headers(credentials)
    cookies = voyager_request_cookies(credentials)
    metadata = http.post_json(
        MEDIA_UPLOAD_URL,
        json={
            "mediaUploadType": "RESUME",
            "fileSize": resume_file.size_bytes,
            "filename": resume_file.filename,
        },
        headers=headers,
        cookies=cookies,
    )
    upload_url, asset_urn = _parse_upload_metadata(metadata)
    content_type = resume_file.content_type.strip() or "application/octet-stream"
    http.put_raw(
        upload_url,
        content=resume_file.data,
        headers={"Content-Type": content_type},
        cookies=cookies,
    )
    return asset_urn


def _parse_upload_metadata(payload: Any) -> tuple[str, str]:
    """Extract Ambry upload URL and asset URN from a media metadata response."""
    value = _unwrap_value(payload)
    if not isinstance(value, dict):
        raise ValueError("linkedin resume upload returned unexpected metadata payload")

    upload_url = _first_string(
        value,
        "singleUploadUrl",
        "uploadUrl",
        "url",
    )
    asset_urn = _first_string(
        value,
        "urn",
        "mediaArtifact",
        "assetUrn",
    )
    if not upload_url or not asset_urn:
        raise ValueError("linkedin resume upload metadata is missing upload URL or asset URN")
    return upload_url, asset_urn


def _unwrap_value(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    data = payload.get("data")
    if isinstance(data, dict) and "value" in data:
        return data["value"]
    if "value" in payload:
        return payload["value"]
    return payload


def _first_string(source: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        raw = source.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None
