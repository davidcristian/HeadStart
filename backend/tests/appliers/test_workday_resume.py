"""Tests for Workday resume upload helpers."""

import json

import httpx
import pytest

from app.appliers.adapters import workday_resume
from app.appliers.adapters.workday_resume import (
    build_resume_attachment_payload,
    preview_resume_attachment,
    upload_resume_attachment,
)
from app.appliers.adapters.workday_target import WorkdayTarget
from app.appliers.resume import workday_content_type
from app.schemas.profile import ResumeFile
from tests.conftest import load_json_fixture, make_http_client


def _unexpected(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected request: {request.method} {request.url}")


def _upload(handler, resume=None):
    return upload_resume_attachment(
        make_http_client(handler),
        target=_target(),
        application_id="app-1",
        resume_file=resume or _resume(),
        job_path="US-CA/Role_JR1",
        csrf_token="csrf",
        session_id="sess",
        credentials=None,
    )


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


def test_preview_resume_attachment_returns_none_without_file() -> None:
    assert preview_resume_attachment(None) is None


def test_preview_resume_attachment_returns_none_when_meta_missing(monkeypatch) -> None:
    monkeypatch.setattr(workday_resume, "resume_meta_for_payload", lambda _f: None)
    assert preview_resume_attachment(_resume()) is None


def test_upload_rejects_non_dict_upload_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "a", "dict"])

    with pytest.raises(ValueError, match="unexpected response"):
        _upload(handler)


def test_upload_surfaces_upload_error_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errorCode": "TOO_LARGE", "message": "file too large"})

    with pytest.raises(ValueError, match="file too large"):
        _upload(handler)


def test_upload_error_code_without_message_uses_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errorCode": "TOO_LARGE"})

    with pytest.raises(ValueError, match="TOO_LARGE"):
        _upload(handler)


def test_upload_requires_file_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"contentType": {"id": "ct"}})

    with pytest.raises(ValueError, match="did not return a file id"):
        _upload(handler)


def test_upload_defaults_content_type_when_missing_then_submits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/attachments"):
            return httpx.Response(200, json={"id": "file-1"})
        if request.url.path.endswith("/resumeattachments"):
            return httpx.Response(200, json={"ok": True})
        return _unexpected(request)

    result = _upload(handler)
    assert result["upload"]["id"] == "file-1"
    assert result["resumeAttachments"]["attachments"][0]["contentType"] == workday_content_type(
        "application/pdf"
    )


def test_upload_submit_http_error_raises_value_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/attachments"):
            return httpx.Response(200, json={"id": "file-1", "contentType": {"id": "ct"}})
        if request.url.path.endswith("/resumeattachments"):
            return httpx.Response(500, text="boom")
        return _unexpected(request)

    with pytest.raises(ValueError):
        _upload(handler)


def test_upload_submit_list_response_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/attachments"):
            return httpx.Response(200, json={"id": "file-1", "contentType": {"id": "ct"}})
        if request.url.path.endswith("/resumeattachments"):
            return httpx.Response(200, json=["rejected"])
        return _unexpected(request)

    with pytest.raises(ValueError, match="rejected the upload"):
        _upload(handler)


def test_upload_submit_error_code_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/attachments"):
            return httpx.Response(200, json={"id": "file-1", "contentType": {"id": "ct"}})
        if request.url.path.endswith("/resumeattachments"):
            return httpx.Response(200, json={"errorCode": "BAD", "message": "invalid"})
        return _unexpected(request)

    with pytest.raises(ValueError, match="invalid"):
        _upload(handler)


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
