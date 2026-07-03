"""Tests for resume template upload validation and storage helpers."""

from __future__ import annotations

import io
import zipfile

import pytest

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.services.profile_resume_template import (
    build_resume_template_stored,
    validate_resume_template_upload,
)

TEX_SOURCE = b"\\documentclass{article}\\begin{document}Hi\\end{document}"


def _zip_files(files: dict[str, str | bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for path, content in files.items():
            payload = content.encode("utf-8") if isinstance(content, str) else content
            archive.writestr(path, payload)
    return buf.getvalue()


def test_validate_accepts_tex_upload() -> None:
    validate_resume_template_upload(
        filename="resume.tex", content_type="application/x-tex", data=TEX_SOURCE
    )


def test_validate_rejects_blank_filename() -> None:
    with pytest.raises(ValidationError, match="filename is required"):
        validate_resume_template_upload(filename="   ", content_type="text/plain", data=TEX_SOURCE)


def test_validate_rejects_empty_data() -> None:
    with pytest.raises(ValidationError, match="empty"):
        validate_resume_template_upload(filename="resume.tex", content_type="text/plain", data=b"")


def test_validate_zip_requires_zip_content_type() -> None:
    with pytest.raises(ValidationError, match="zip archive"):
        validate_resume_template_upload(
            filename="bundle.zip", content_type="text/plain", data=b"PK\x03\x04"
        )


def test_validate_zip_rejects_oversized_bundle(monkeypatch) -> None:
    monkeypatch.setattr(settings, "profile_resume_template_bundle_max_bytes", 2)
    with pytest.raises(ValidationError, match="MB limit"):
        validate_resume_template_upload(
            filename="bundle.zip", content_type="application/zip", data=b"PK\x03\x04longer"
        )


def test_validate_zip_accepts_valid_bundle() -> None:
    validate_resume_template_upload(
        filename="bundle.zip", content_type="application/zip", data=b"PK\x03\x04"
    )


def test_validate_rejects_unknown_extension() -> None:
    with pytest.raises(ValidationError, match=".tex file or .zip"):
        validate_resume_template_upload(
            filename="resume.pdf", content_type="text/plain", data=TEX_SOURCE
        )


def test_validate_tex_rejects_wrong_content_type() -> None:
    with pytest.raises(ValidationError, match="LaTeX source"):
        validate_resume_template_upload(
            filename="resume.tex", content_type="application/pdf", data=TEX_SOURCE
        )


def test_validate_tex_rejects_oversized(monkeypatch) -> None:
    monkeypatch.setattr(settings, "profile_resume_template_max_bytes", 2048)
    with pytest.raises(ValidationError, match="KB limit"):
        validate_resume_template_upload(
            filename="resume.tex", content_type="text/plain", data=b"x" * 4096
        )


def test_validate_tex_rejects_non_utf8() -> None:
    with pytest.raises(ValidationError, match="UTF-8"):
        validate_resume_template_upload(
            filename="resume.tex", content_type="text/plain", data=b"\xff\xfe\x00bad"
        )


def test_build_stored_single_tex() -> None:
    stored = build_resume_template_stored(
        filename="resume.tex", content_type="text/plain", data=TEX_SOURCE
    )
    assert stored.filename == "resume.tex"
    assert stored.format == "single"


def test_build_stored_bundle_zip() -> None:
    data = _zip_files(
        {
            "main.tex": r"\documentclass{article}\begin{document}Hi\end{document}",
            "style.sty": r"\ProvidesPackage{style}",
        }
    )
    stored = build_resume_template_stored(
        filename="bundle.zip", content_type="application/zip", data=data
    )
    assert stored.format == "bundle"
    assert stored.entrypoint == "main.tex"
    assert stored.file_count == 2
