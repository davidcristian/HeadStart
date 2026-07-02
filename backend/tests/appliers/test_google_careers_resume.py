"""Tests for Google Careers resume upload helpers."""

import base64
import re
from urllib.parse import parse_qs, urlparse

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.google_careers import GoogleCareersApplier
from app.appliers.adapters.google_careers_payload import build_careers_profile
from app.appliers.adapters.google_careers_resume import (
    DEFAULT_UPLOAD_URL,
    GoogleCareersResumeAttachment,
    build_upload_headers,
    parse_upload_response,
    preview_resume_upload,
    sapisidhash_headers,
    upload_resume_attachment,
)
from app.schemas.profile import ProfileData, ResumeFile
from tests.conftest import load_fixture, make_http_client

_JOB_URL = (
    "https://www.google.com/about/careers/applications/jobs/results/"
    "72271215732892358-software-engineer-mobile-ios-google-photos"
)


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="London, UK",
        resume_text="Experienced engineer.",
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        answers={"work_authorization": "Yes"},
    )


def _google_credentials() -> dict[str, dict[str, str]]:
    return {
        "cookies": {"SID": "sid-value", "SAPISID": "sapisid-value"},
        "headers": {},
        "session": {"at": "csrf-token-abc"},
    }


def _resume() -> ResumeFile:
    return ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=len(b"%PDF-1.4 test"),
        data=b"%PDF-1.4 test",
    )


def _encode_string_field(field_number: int, value: str) -> bytes:
    tag = (field_number << 3) | 2
    encoded = value.encode("utf-8")
    return bytes([tag, len(encoded)]) + encoded


def _encode_attachment_response(attachment_id: str, filename: str) -> str:
    inner = _encode_string_field(1, attachment_id) + _encode_string_field(2, filename)
    outer = bytes([(1 << 3) | 2, len(inner)]) + inner
    return base64.b64encode(outer).decode("ascii")


def test_preview_resume_upload_returns_scotty_metadata() -> None:
    preview = preview_resume_upload(_resume())
    assert preview is not None
    assert preview["upload_url"] == DEFAULT_UPLOAD_URL
    assert preview["filename"] == "resume.pdf"
    assert preview["parse_resume"] is False


def test_parse_upload_response_decodes_base64_protobuf() -> None:
    body = _encode_attachment_response("attach-123", "resume.pdf")
    attachment = parse_upload_response(body)
    assert attachment == GoogleCareersResumeAttachment(
        attachment_id="attach-123",
        filename="resume.pdf",
    )


def test_sapisidhash_headers_uses_sapisid_cookie() -> None:
    headers = sapisidhash_headers({"SAPISID": "secret-token"})
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("SAPISIDHASH ")
    assert re.fullmatch(r"SAPISIDHASH \d+_[0-9a-f]{40}", headers["Authorization"])


def test_build_upload_headers_sets_scotty_start_command() -> None:
    headers = build_upload_headers(_resume(), parse_resume=False)
    assert headers["X-Goog-Upload-Command"] == "start"
    assert headers["X-Goog-Upload-Protocol"] == "resumable"
    assert headers["parseResume"] == "false"
    assert headers["X-Goog-Upload-File-Name"] == "resume.pdf"


def test_upload_resume_attachment_runs_start_then_finalize() -> None:
    session_url = "https://www.google.com/about/careers/attachmentupload/upload/session-abc"
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        headers = {k.lower(): v for k, v in request.headers.items()}
        if str(request.url) == DEFAULT_UPLOAD_URL:
            seen["start_headers"] = headers
            return httpx.Response(
                200,
                headers={"X-Goog-Upload-URL": session_url},
                text="",
            )
        if str(request.url) == session_url:
            seen["finalize_headers"] = headers
            seen["finalize_body"] = request.content
            body = _encode_attachment_response("attach-live-001", "resume")
            return httpx.Response(200, text=body)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    attachment = upload_resume_attachment(
        make_http_client(handler),
        _resume(),
        credentials={"cookies": {"SAPISID": "secret-token"}, "headers": {}, "session": {}},
    )

    assert attachment.attachment_id == "attach-live-001"
    assert attachment.filename == "resume.pdf"
    start_headers = seen["start_headers"]
    finalize_headers = seen["finalize_headers"]
    assert isinstance(start_headers, dict)
    assert isinstance(finalize_headers, dict)
    assert start_headers["x-goog-upload-command"] == "start"
    assert finalize_headers["x-goog-upload-command"] == "upload, finalize"
    assert finalize_headers["x-goog-upload-offset"] == "0"
    assert seen["finalize_body"] == _resume().data


def test_build_careers_profile_includes_resume_attachment() -> None:
    payload = build_careers_profile(
        _profile(),
        resume_attachment=GoogleCareersResumeAttachment(
            attachment_id="attach-123",
            filename="resume.pdf",
        ),
    )
    assert payload["resumeAttachment"] == {"id": "attach-123", "name": "resume.pdf"}


def test_live_submit_uploads_resume_before_batchexecute() -> None:
    job_html = load_fixture("google_careers_job_detail.html")
    apply_html = load_fixture("google_careers_apply_page.html")
    session_url = "https://www.google.com/about/careers/attachmentupload/upload/session-xyz"
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == DEFAULT_UPLOAD_URL:
            seen["upload_start"] = True
            return httpx.Response(200, headers={"X-Goog-Upload-URL": session_url}, text="")
        if url == session_url:
            seen["upload_finalize"] = request.content
            body = _encode_attachment_response("attach-live-001", "resume")
            return httpx.Response(200, text=body)
        if "/jobs/results/" in url:
            return httpx.Response(200, text=job_html)
        if "/applications/apply" in url and "batchexecute" not in url:
            return httpx.Response(200, text=apply_html)
        if "batchexecute" in url:
            params = parse_qs(urlparse(url).query)
            rpc_id = params["rpcids"][0]
            if rpc_id == "qvYBjf":
                body = load_fixture("google_careers_batchexecute_save_profile.txt")
            elif rpc_id == "tBY1Qe":
                body = load_fixture("google_careers_batchexecute_create_packet.txt")
            elif rpc_id == "o6YK3":
                body = load_fixture("google_careers_batchexecute_save_packet.txt")
            elif rpc_id == "pmtdJd":
                body = load_fixture("google_careers_batchexecute_submit_packet.txt")
            else:
                raise AssertionError(f"unexpected rpc id {rpc_id}")
            return httpx.Response(200, text=body)
        raise AssertionError(f"unexpected request {request.method} {url}")

    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    applier = GoogleCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="72271215732892358",
            job_title="Software Engineer",
            company="Google",
            job_url=_JOB_URL,
            config={},
            profile=_profile(),
            credentials=_google_credentials(),
            resume_file=resume,
            dry_run=False,
        )
    )

    assert result.status == "submitted"
    assert seen.get("upload_start") is True
    assert seen.get("upload_finalize") == b"%PDF"
    assert result.payload is not None
    assert result.payload["resume_attachment"] == {
        "id": "attach-live-001",
        "name": "resume.pdf",
    }
    assert result.payload["careers_profile"]["resumeAttachment"] == {
        "id": "attach-live-001",
        "name": "resume.pdf",
    }


def test_upload_resume_attachment_rejects_empty_file() -> None:
    empty = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=0,
        data=b"",
    )
    try:
        upload_resume_attachment(make_http_client(_unexpected_request), empty)
    except ValueError as exc:
        assert "non-empty" in str(exc)
    else:
        raise AssertionError("expected ValueError for empty resume")


def _unexpected_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")
