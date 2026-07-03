"""Decode tailored resume PDFs passed into the apply flow."""

from __future__ import annotations

import base64
import binascii

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.schemas.profile import ResumeFile
from app.services.application_artifacts import ApplicationArtifactService


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


def resolve_tailored_resume_for_apply(
    session: Session,
    user_id: int,
    *,
    tailored_resume_b64: str | None,
    tailored_resume_artifact_id: int | None,
) -> tuple[ResumeFile | None, int | None]:
    """Load or persist a tailored resume for one apply attempt."""
    artifacts = ApplicationArtifactService(session)
    if tailored_resume_artifact_id is not None:
        resume = artifacts.load_tailored_resume_pdf(user_id, tailored_resume_artifact_id)
        return resume, tailored_resume_artifact_id

    tailored_resume = decode_tailored_resume(tailored_resume_b64)
    if tailored_resume is None:
        return None, None

    artifact = artifacts.store_tailored_resume_pdf(
        user_id,
        data=tailored_resume.data,
        filename=tailored_resume.filename,
        content_type=tailored_resume.content_type,
    )
    return tailored_resume, artifact.id
