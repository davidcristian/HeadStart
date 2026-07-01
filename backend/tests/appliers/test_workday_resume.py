"""Tests for Workday resume upload helpers."""

import json

import httpx

from app.appliers.adapters.workday_resume import (
    build_resume_attachment_payload,
    preview_resume_attachment,
    upload_resume_attachment,
)
from app.appliers.adapters.workday_target import WorkdayTarget
from app.appliers.resume import workday_content_type
from app.schemas.profile import ResumeFile
from tests.conftest import load_json_fixture, make_http_client


def _target() -> WorkdayTarget:
    return WorkdayTarget(
        tenant="acme",
        site="AcmeCareers",
        region="wd5",
        locale="en-US",
        company="ACME",
        host="acme.wd5.myworkdayjobs.com",
    )


def _resume() -> ResumeFile:
    return ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=len(b"%PDF-1.4 test"),
        data=b"%PDF-1.4 test",
    )


def test_workday_content_type_maps_mime() -> None:
    assert workday_content_type("application/pdf") == {
        "id": "Content_Type_ID=application/pdf",
        "descriptor": "pdf",
    }


def test_preview_resume_attachment_omits_file_id() -> None:
    preview = preview_resume_attachment(_resume())
    assert preview is not None
    assert preview["attachments"][0]["fileName"] == "resume.pdf"
    assert "file" not in preview["attachments"][0]


def test_upload_resume_attachment_posts_file_then_resumeattachments() -> None:
    upload_fixture = load_json_fixture("workday_attachment_upload.json")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["last_url"] = str(request.url)
        seen["last_method"] = request.method
        if request.url.path.endswith("/attachments"):
            seen["attachments_multipart"] = request.read()
            return httpx.Response(200, json=upload_fixture)
        if request.url.path.endswith("/resumeattachments"):
            seen["resumeattachments_body"] = json.loads(request.read().decode())
            return httpx.Response(200, json={"ok": True})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    result = upload_resume_attachment(
        make_http_client(handler),
        target=_target(),
        application_id="app-abc123",
        resume_file=_resume(),
        job_path="US-CA-Santa-Clara/Senior-Software-Engineer_JR1001",
        csrf_token="csrf-token",
        session_id="sess-xyz789",
        credentials={
            "cookies": {
                "CALYPSO_SESSION": "session-token",
                "CALYPSO_CSRF_TOKEN": "csrf-token",
            },
            "headers": {},
            "session": {},
        },
    )

    assert result["upload"]["id"] == "file-resume-001"
    body = seen["resumeattachments_body"]
    assert isinstance(body, dict)
    assert body == build_resume_attachment_payload(
        _resume(),
        uploaded_file_id="file-resume-001",
        content_type=upload_fixture["contentType"],
    )
    multipart = seen["attachments_multipart"]
    assert isinstance(multipart, bytes)
    assert b'name="body"' in multipart
    assert b"resume.pdf" in multipart
    assert seen["last_method"] == "POST"
    url = seen["last_url"]
    assert isinstance(url, str)
    assert url.endswith("/jobapplication/app-abc123/resumeattachments")
