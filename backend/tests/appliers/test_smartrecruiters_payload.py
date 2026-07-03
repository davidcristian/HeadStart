"""Tests for SmartRecruiters candidate payload builders."""

import pytest

from app.appliers.adapters.smartrecruiters_payload import (
    build_application_payload,
    build_message_to_hiring_manager,
    extract_application_id,
    extract_error_message,
)
from app.schemas.profile import ApplyProfile, ProfileData, ProfileLinks, ResumeFile


def _resume() -> ResumeFile:
    return ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )


def test_build_message_uses_cover_letter_override() -> None:
    profile = ProfileData(full_name="Ada", email="a@example.com")
    assert (
        build_message_to_hiring_manager(
            profile, company="ACME", job_title="Role", cover_letter="Hi"
        )
        == "Hi"
    )


def test_build_message_blank_template_and_no_resume_text_returns_none() -> None:
    profile = ProfileData(full_name="Ada", email="a@example.com", cover_letter_template="  ")
    assert (
        build_message_to_hiring_manager(
            profile, company="ACME", job_title="Role", cover_letter=None
        )
        is None
    )


def test_build_message_excludes_resume_text_when_disabled() -> None:
    profile = ProfileData(
        full_name="Ada",
        email="a@example.com",
        resume_text="my resume",
        cover_letter_template="Dear team",
    )
    message = build_message_to_hiring_manager(
        profile,
        company="ACME",
        job_title="Role",
        cover_letter=None,
        include_resume_text=False,
    )
    assert message == "Dear team"


def test_build_application_payload_requires_name_and_email() -> None:
    with pytest.raises(ValueError, match="full_name and email"):
        build_application_payload(
            ProfileData(full_name="", email=""),
            company="ACME",
            job_title="Role",
            config={},
            configuration=None,
        )


def test_build_application_payload_minimal_profile_omits_optionals() -> None:
    payload = build_application_payload(
        ProfileData(full_name="Ada", email="a@example.com"),
        company="ACME",
        job_title="Role",
        config={},
        configuration=None,
    )
    assert "phoneNumber" not in payload
    assert "location" not in payload
    assert "web" not in payload
    assert "messageToHiringManager" not in payload
    assert "consentDecisions" not in payload
    assert "answers" not in payload
    assert "resume" not in payload


def test_build_application_payload_website_only_web() -> None:
    payload = build_application_payload(
        ProfileData(
            full_name="Ada",
            email="a@example.com",
            links=ProfileLinks(website="https://ada.example"),
        ),
        company="ACME",
        job_title="Role",
        config={},
        configuration=None,
    )
    assert payload["web"] == {"website": "https://ada.example"}


def test_build_application_payload_resume_meta_without_bytes() -> None:
    profile = ApplyProfile(
        full_name="Ada",
        email="a@example.com",
        exists=True,
        resume_file=_resume(),
    )
    payload = build_application_payload(
        profile,
        company="ACME",
        job_title="Role",
        config={},
        configuration=None,
        include_file_bytes=False,
    )
    assert payload["resume_file"]["filename"] == "resume.pdf"
    assert "resume" not in payload


def test_extract_application_id_non_dict() -> None:
    assert extract_application_id("nope") is None
    assert extract_application_id({}) is None


def test_extract_error_message_variants() -> None:
    assert extract_error_message({"message": "boom"}) == "boom"
    assert extract_error_message({"errors": ["a", "b"]}) == "a; b"
    assert extract_error_message({}) == "smartrecruiters apply rejected the submission"
    assert extract_error_message("nope") == "smartrecruiters apply rejected the submission"
