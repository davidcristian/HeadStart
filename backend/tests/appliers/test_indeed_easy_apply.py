"""Tests for Indeed-hosted Easy Apply payload helpers."""

from __future__ import annotations

import pytest

from app.appliers.adapters.indeed_detail import IndeedJobDetail
from app.appliers.adapters.indeed_easy_apply import (
    _cover_letter_text,
    build_easy_apply_payload,
    build_smartapply_url,
    build_submit_body,
    has_indeed_session_cookies,
)
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile


def _detail(**overrides: object) -> IndeedJobDetail:
    base: dict[str, object] = {
        "job_key": "jk-1",
        "title": "Engineer",
        "company": "ACME",
        "external_apply_url": None,
        "easily_apply": True,
        "indeed_applyable_job_id": None,
        "apply_continue_url": None,
        "expired": False,
    }
    base.update(overrides)
    return IndeedJobDetail(**base)  # type: ignore[arg-type]


def test_build_smartapply_url_prefers_applyable_id() -> None:
    assert "indeedApplyableJobId=applyable-1" in build_smartapply_url(
        _detail(indeed_applyable_job_id="applyable-1")
    )


def test_build_smartapply_url_falls_back_to_job_key() -> None:
    assert "jk=jk-1" in build_smartapply_url(_detail())


def test_build_easy_apply_payload_requires_name_and_email() -> None:
    with pytest.raises(ValueError, match="full_name and email"):
        build_easy_apply_payload(
            _detail(),
            ProfileData(full_name="", email=""),
            company="ACME",
            job_title="Role",
            cover_letter=None,
            resume_file=None,
        )


def test_build_easy_apply_payload_minimal_omits_optionals() -> None:
    payload = build_easy_apply_payload(
        _detail(),
        ProfileData(full_name="Ada", email="a@example.com"),
        company="ACME",
        job_title="Role",
        cover_letter=None,
        resume_file=None,
    )
    applicant = payload["applicant"]
    assert "indeedApplyableJobId" not in payload
    assert "continueUrl" not in payload
    assert "phoneNumber" not in applicant
    assert "location" not in applicant
    assert "coverLetter" not in payload
    assert "answers" not in payload


def test_build_easy_apply_payload_includes_all_fields_and_answers() -> None:
    payload = build_easy_apply_payload(
        _detail(indeed_applyable_job_id="a-1", apply_continue_url="https://continue"),
        ProfileData(
            full_name="Ada Lovelace",
            email="a@example.com",
            phone="+1 555",
            location="Remote",
            resume_text="my resume",
            answers={"q1": "yes", "blank": ""},
        ),
        company="ACME",
        job_title="Role",
        cover_letter="Custom",
        resume_file=None,
    )
    assert payload["indeedApplyableJobId"] == "a-1"
    assert payload["continueUrl"] == "https://continue"
    assert payload["applicant"]["phoneNumber"] == "+1 555"
    assert payload["applicant"]["location"] == "Remote"
    assert payload["coverLetter"] == "Custom"
    assert payload["resumeText"] == "my resume"
    assert payload["answers"] == {"q1": "yes"}


def test_build_easy_apply_payload_uses_apply_profile_resume() -> None:
    resume = ResumeFile(
        filename="resume.pdf", content_type="application/pdf", size_bytes=4, data=b"%PDF"
    )
    profile = ApplyProfile(
        full_name="Ada",
        email="a@example.com",
        resume_text="text",
        exists=True,
        resume_file=resume,
    )
    payload = build_easy_apply_payload(
        _detail(),
        profile,
        company="ACME",
        job_title="Role",
        cover_letter=None,
        resume_file=None,
    )
    # With a resume file present, resumeText is omitted and resume_file meta added.
    assert "resumeText" not in payload
    assert payload["resume_file"]["filename"] == "resume.pdf"


def test_build_submit_body_without_resume_keeps_resume_text() -> None:
    payload = {
        "jobKey": "jk-1",
        "applicant": {"firstName": "Ada", "email": "a@example.com"},
        "resumeText": "my resume",
    }
    body = build_submit_body(payload, resume_file=None)
    assert body["resumeText"] == "my resume"
    assert "resume" not in body["applicant"]


def test_has_indeed_session_cookies_variants() -> None:
    assert has_indeed_session_cookies(None) is False
    assert has_indeed_session_cookies({"cookies": {}}) is False
    assert has_indeed_session_cookies({"cookies": {"PPID": "x"}}) is True


def test_cover_letter_text_override_and_blank_template() -> None:
    assert (
        _cover_letter_text(
            ProfileData(full_name="Ada", email="a@example.com"),
            company="ACME",
            job_title="Role",
            cover_letter="Hi there",
        )
        == "Hi there"
    )
    assert (
        _cover_letter_text(
            ProfileData(full_name="Ada", email="a@example.com", cover_letter_template="  "),
            company="ACME",
            job_title="Role",
            cover_letter=None,
        )
        is None
    )
