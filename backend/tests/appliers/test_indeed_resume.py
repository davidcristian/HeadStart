"""Tests for Indeed-hosted resume file attachments on live apply."""

from __future__ import annotations

import json

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.indeed import IndeedApplier
from app.appliers.adapters.indeed_detail import parse_viewjob_page
from app.appliers.adapters.indeed_easy_apply import build_easy_apply_payload, build_submit_body
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile
from tests.conftest import load_fixture, make_http_client


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="Remote",
        resume_text="Experienced engineer.",
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
    )


def test_hosted_live_submit_includes_resume_file_bytes() -> None:
    viewjob = load_fixture("indeed_viewjob_hosted.html")
    apply_success = load_fixture("indeed_apply_success.json")
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "viewjob" in url:
            return httpx.Response(200, text=viewjob)
        if "smartapply.indeed.com" in url:
            seen["method"] = request.method
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                text=apply_success,
                headers={"content-type": "application/json"},
            )
        raise AssertionError(f"unexpected network call: {request.method} {url}")

    applier = IndeedApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="hostedjobkey001",
            job_title="Customer Support Specialist",
            company="Hosted Co",
            job_url="https://www.indeed.com/viewjob?jk=hostedjobkey001",
            config={"accept_private_api_risk": True},
            profile=profile,
            resume_file=resume,
            credentials={
                "cookies": {"PPID": "test", "SOCK": "session"},
                "session": {"csrf_token": "csrf-1"},
                "headers": {},
            },
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    body = seen["body"]
    assert isinstance(body, dict)
    resume_file = body["applicant"]["resume"]["file"]
    assert resume_file["fileName"] == "resume.pdf"
    assert resume_file["contentType"] == "application/pdf"
    assert "resumeText" not in body


def test_build_submit_body_attaches_resume_file() -> None:
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    detail = parse_viewjob_page(load_fixture("indeed_viewjob_hosted.html"))
    assert detail is not None
    payload = build_easy_apply_payload(
        detail,
        _profile(),
        company="Hosted Co",
        job_title="Customer Support Specialist",
        cover_letter=None,
        resume_file=resume,
    )
    body = build_submit_body(payload, resume_file=resume)
    assert body["applicant"]["resume"]["file"]["fileName"] == "resume.pdf"
    assert "resumeText" not in body
