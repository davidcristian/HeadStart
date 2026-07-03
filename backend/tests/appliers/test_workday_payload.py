"""Tests for Workday CXS application payload builders."""

import pytest

from app.appliers.adapters.workday_payload import (
    build_application_payload,
    build_name_body,
    build_supplemental_text,
)
from app.schemas.profile import ProfileData, ProfileLinks


def _profile(**overrides: object) -> ProfileData:
    base: dict[str, object] = {
        "full_name": "Ada Lovelace",
        "email": "ada@example.com",
    }
    base.update(overrides)
    return ProfileData(**base)


def test_build_supplemental_text_prefers_cover_letter_override() -> None:
    text = build_supplemental_text(
        _profile(cover_letter_template="Template body."),
        company="ACME",
        job_title="Engineer",
        cover_letter="  Custom letter.  ",
    )
    assert text == "Custom letter."


def test_build_supplemental_text_renders_template_and_resume() -> None:
    text = build_supplemental_text(
        _profile(
            cover_letter_template="Dear {company}, I want {job_title}.",
            resume_text="Experienced engineer.",
        ),
        company="ACME",
        job_title="Engineer",
        cover_letter=None,
    )
    assert text is not None
    assert "Dear ACME, I want Engineer." in text
    assert "Resume:\nExperienced engineer." in text


def test_build_supplemental_text_returns_none_when_empty() -> None:
    assert (
        build_supplemental_text(
            _profile(),
            company="ACME",
            job_title="Engineer",
            cover_letter=None,
        )
        is None
    )


def test_build_supplemental_text_omits_resume_when_disabled() -> None:
    text = build_supplemental_text(
        _profile(resume_text="Experienced engineer."),
        company="ACME",
        job_title="Engineer",
        cover_letter=None,
        include_resume_text=False,
    )
    assert text is None


def test_build_application_payload_requires_first_and_last_name() -> None:
    with pytest.raises(ValueError, match="first and last name"):
        build_application_payload(
            ProfileData(full_name="Ada", email="ada@example.com"),
            job_posting_id="job-1",
            job_path="loc/job-1",
            job_title="Role",
            company="ACME",
            config={},
        )


def test_build_application_payload_requires_email() -> None:
    with pytest.raises(ValueError, match="email is required"):
        build_application_payload(
            ProfileData(full_name="Ada Lovelace", email="   "),
            job_posting_id="job-1",
            job_path="loc/job-1",
            job_title="Role",
            company="ACME",
            config={},
        )


def test_build_application_payload_includes_optional_fields() -> None:
    payload = build_application_payload(
        _profile(
            phone="+1 555 0100",
            location="San Francisco",
            links=ProfileLinks(
                linkedin="https://linkedin.com/in/ada",
                github="https://github.com/ada",
                website="https://ada.example",
            ),
            answers={"q1": "yes", "q2": ""},
        ),
        job_posting_id="job-1",
        job_path="loc/job-1",
        job_title="Role",
        company="ACME",
        config={"country_id": "GB", "apply_method": "auto"},
    )
    candidate = payload["candidate"]
    assert candidate["phoneNumber"] == "+1 555 0100"
    assert candidate["location"] == "San Francisco"
    assert candidate["links"] == {
        "linkedIn": "https://linkedin.com/in/ada",
        "github": "https://github.com/ada",
        "website": "https://ada.example",
    }
    assert candidate["legalName"]["country"]["id"] == "GB"
    assert payload["applyMethod"] == "auto"
    assert payload["answers"] == {"q1": "yes"}


def test_build_application_payload_omits_empty_optionals() -> None:
    payload = build_application_payload(
        _profile(),
        job_posting_id="job-1",
        job_path="loc/job-1",
        job_title="Role",
        company="ACME",
        config={},
    )
    candidate = payload["candidate"]
    assert "phoneNumber" not in candidate
    assert "location" not in candidate
    assert "links" not in candidate
    assert "answers" not in payload


def test_build_name_body_defaults_country() -> None:
    body = build_name_body(_profile(), {})
    assert body["legalName"]["firstName"] == "Ada"
    assert body["legalName"]["lastName"] == "Lovelace"
    assert body["legalName"]["country"]["id"] == "US"
    assert body["preferredCheck"] is False
