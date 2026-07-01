"""Tests for shared resume attachment helpers."""

import base64

from app.appliers.resume import (
    greenhouse_resume_fields,
    lever_resume_part,
    resume_meta_for_payload,
    workday_content_type,
)
from app.schemas.profile import ResumeFile


def test_greenhouse_resume_fields() -> None:
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    fields = greenhouse_resume_fields(resume)
    assert fields["resume_content_filename"] == "resume.pdf"
    assert base64.b64decode(fields["resume_content"]) == b"%PDF"


def test_lever_resume_part() -> None:
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    field, value = lever_resume_part(resume) or ("", ())
    assert field == "resume"
    assert value[0] == "resume.pdf"
    assert value[1] == b"%PDF"


def test_resume_meta_for_payload_omits_bytes() -> None:
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    meta = resume_meta_for_payload(resume)
    assert meta is not None
    assert meta["filename"] == "resume.pdf"
    assert "data" not in meta


def test_workday_content_type_uses_octet_stream_fallback() -> None:
    assert workday_content_type("")["id"] == "Content_Type_ID=application/octet-stream"
