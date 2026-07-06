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


def test_indeed_resume_file_fields_base64_encodes_bytes() -> None:
    from app.appliers.resume import indeed_resume_file_fields

    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    fields = indeed_resume_file_fields(resume)
    assert fields["fileName"] == "resume.pdf"
    assert fields["contentType"] == "application/pdf"
    assert base64.b64decode(fields["data"]) == b"%PDF"


def test_workday_content_type_uses_octet_stream_fallback() -> None:
    assert workday_content_type("")["id"] == "Content_Type_ID=application/octet-stream"


def test_resume_meta_for_payload_returns_none_without_file() -> None:
    assert resume_meta_for_payload(None) is None


def test_greenhouse_resume_fields_empty_without_file() -> None:
    assert greenhouse_resume_fields(None) == {}


def test_lever_resume_part_none_without_file() -> None:
    assert lever_resume_part(None) is None


def test_indeed_resume_file_fields_octet_stream_fallback() -> None:
    from app.appliers.resume import indeed_resume_file_fields

    resume = ResumeFile(
        filename="resume.pdf",
        content_type="  ",
        size_bytes=4,
        data=b"%PDF",
    )
    assert indeed_resume_file_fields(resume)["contentType"] == "application/octet-stream"


def test_flatten_lever_form_fields_handles_urls_consent_bool_scalar() -> None:
    from app.appliers.resume import flatten_lever_form_fields

    parts = flatten_lever_form_fields(
        {
            "urls": {"LinkedIn": "https://linkedin.com/in/ada"},
            "consent": {"marketing": True},
            "opt_in": True,
            "opt_out": False,
            "name": "Ada",
        }
    )
    assert parts["urls[LinkedIn]"] == "https://linkedin.com/in/ada"
    assert parts["consent"] == '{"marketing": true}'
    assert parts["opt_in"] == "true"
    assert parts["opt_out"] == "false"
    assert parts["name"] == "Ada"


def test_flatten_lever_form_fields_skips_resume_file_metadata() -> None:
    """APL-13: do not stringify resume_file meta beside the multipart resume part."""
    from app.appliers.resume import flatten_lever_form_fields

    parts = flatten_lever_form_fields(
        {
            "name": "Ada",
            "resume_file": {
                "filename": "resume.pdf",
                "content_type": "application/pdf",
                "size_bytes": 4,
            },
        }
    )
    assert parts == {"name": "Ada"}
    assert "resume_file" not in parts
