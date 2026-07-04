"""Resume template upload validation and storage helpers."""

from __future__ import annotations

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.resumes.latex_safety import reject_dangerous_latex_content
from app.resumes.template_bundle import parse_template_bundle
from app.schemas.profile import (
    ALLOWED_RESUME_TEMPLATE_BUNDLE_CONTENT_TYPES,
    ALLOWED_RESUME_TEMPLATE_CONTENT_TYPES,
    ResumeTemplateStored,
)


def validate_resume_template_upload(*, filename: str, content_type: str, data: bytes) -> None:
    """Reject invalid LaTeX template uploads before encryption."""
    name = filename.strip()
    if not name:
        raise ValidationError("Resume template filename is required")
    if len(data) == 0:
        raise ValidationError("Resume template file is empty")
    lower = name.lower()
    if lower.endswith(".zip"):
        if content_type not in ALLOWED_RESUME_TEMPLATE_BUNDLE_CONTENT_TYPES:
            raise ValidationError("Resume template bundle must be a .zip archive (application/zip)")
        max_bytes = settings.profile_resume_template_bundle_max_bytes
        if len(data) > max_bytes:
            raise ValidationError(
                f"Resume template bundle exceeds the {max_bytes // 1_048_576} MB limit"
            )
        return
    if not lower.endswith(".tex"):
        raise ValidationError("Resume template must be a .tex file or .zip bundle")
    if content_type not in ALLOWED_RESUME_TEMPLATE_CONTENT_TYPES:
        raise ValidationError(
            "Resume template must be LaTeX source (application/x-tex or text/plain)"
        )
    max_bytes = settings.profile_resume_template_max_bytes
    if len(data) > max_bytes:
        raise ValidationError(f"Resume template exceeds the {max_bytes // 1024} KB limit")
    try:
        tex = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("Resume template must be valid UTF-8 text") from exc
    reject_dangerous_latex_content(tex, label=name)


def build_resume_template_stored(
    *,
    filename: str,
    content_type: str,
    data: bytes,
) -> ResumeTemplateStored:
    """Parse and encode a resume template for encrypted profile storage."""
    _ = content_type
    name = filename.strip()
    if name.lower().endswith(".zip"):
        bundle = parse_template_bundle(data)
        return ResumeTemplateStored.from_bundle_zip(
            filename=name,
            data=data,
            entrypoint=bundle.entrypoint,
            file_count=len(bundle.files),
        )
    return ResumeTemplateStored.from_single_tex(filename=name, data=data)
