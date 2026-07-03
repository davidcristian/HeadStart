"""Decode tailored resume PDFs passed into the apply flow."""

from __future__ import annotations

import base64
import binascii

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.schemas.profile import ResumeFile


def decode_tailored_resume(data_b64: str | None) -> ResumeFile | None:
    """Validate and decode an optional base64-encoded tailored resume PDF."""
    if data_b64 is None:
        return None
    raw_input = data_b64.strip()
    if not raw_input:
        return None
    try:
        raw = base64.b64decode(raw_input, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValidationError("Tailored resume must be valid base64") from exc
    max_bytes = settings.profile_resume_max_bytes
    if len(raw) == 0:
        raise ValidationError("Tailored resume PDF is empty")
    if len(raw) > max_bytes:
        raise ValidationError(f"Tailored resume exceeds the {max_bytes // 1_048_576} MB limit")
    if not raw.startswith(b"%PDF"):
        raise ValidationError("Tailored resume must be a PDF")
    return ResumeFile(
        filename="resume-tailored.pdf",
        content_type="application/pdf",
        size_bytes=len(raw),
        data=raw,
    )
