"""Tests for Microsoft Careers SmartApply payload builders."""

import pytest

from app.appliers.adapters.microsoft_careers_payload import (
    _location_detail,
    _question_sections,
    build_answers,
    build_application_payload,
    build_candidate,
)
from app.schemas.profile import ProfileData, ProfileLinks


def test_build_candidate_requires_first_and_last_name() -> None:
    with pytest.raises(ValueError, match="first and last name"):
        build_candidate(
            ProfileData(full_name="Ada", email="a@example.com"),
            job_title="Role",
            company="ACME",
        )


def test_build_candidate_requires_email() -> None:
    with pytest.raises(ValueError, match="email"):
        build_candidate(
            ProfileData(full_name="Ada Lovelace", email=""),
            job_title="Role",
            company="ACME",
        )


def test_build_candidate_minimal_omits_optionals() -> None:
    candidate = build_candidate(
        ProfileData(full_name="Ada Lovelace", email="a@example.com"),
        job_title="Role",
        company="ACME",
    )
    assert "phone" not in candidate
    assert "location" not in candidate
    assert "linkedinUrl" not in candidate
    assert "summary" not in candidate


def test_build_candidate_includes_linkedin_and_summary() -> None:
    candidate = build_candidate(
        ProfileData(
            full_name="Ada Lovelace",
            email="a@example.com",
            links=ProfileLinks(linkedin="https://linkedin.com/in/ada"),
            cover_letter_template="Dear {company}",
        ),
        job_title="Role",
        company="ACME",
    )
    assert candidate["linkedinUrl"] == "https://linkedin.com/in/ada"
    assert candidate["summary"] == "Dear ACME"


def test_build_answers_skips_non_dict_questions_and_missing_ids() -> None:
    questions = {
        "default": {
            "fields": [
                {"questions": ["not a dict", {"questionId": "", "x": 1}, {"questionId": "q1"}]}
            ]
        }
    }
    profile = ProfileData(full_name="Ada", email="a@example.com", answers={"q1": "yes"})
    assert build_answers(profile, questions) == {"q1": "yes"}


def test_cover_letter_falls_back_to_resume_text() -> None:
    candidate = build_candidate(
        ProfileData(full_name="Ada Lovelace", email="a@example.com", resume_text="my resume"),
        job_title="Role",
        company="ACME",
    )
    assert candidate["summary"] == "my resume"


def test_cover_letter_override_wins() -> None:
    candidate = build_candidate(
        ProfileData(full_name="Ada Lovelace", email="a@example.com"),
        job_title="Role",
        company="ACME",
        cover_letter="Custom letter",
    )
    assert candidate["summary"] == "Custom letter"


def test_location_detail_variants() -> None:
    assert _location_detail("City, State, Country") == {
        "city": "City",
        "state": "State",
        "country": "Country",
    }
    assert _location_detail("City, State") == {"city": "City", "state": "State"}
    assert _location_detail("City") == {"city": "City"}
    assert _location_detail("  ") == {}


def test_question_sections_variants() -> None:
    assert _question_sections({}) == []
    assert _question_sections({"default": "nope"}) == []
    assert _question_sections({"fields": [{"a": 1}, "bad"]}) == [{"a": 1}]
    assert _question_sections({"default": {"fields": [{"a": 1}]}}) == [{"a": 1}]


def test_build_application_payload_with_resume_bytes() -> None:
    from app.schemas.profile import ResumeFile

    resume = ResumeFile(
        filename="r.pdf", content_type="application/pdf", size_bytes=4, data=b"%PDF"
    )
    payload = build_application_payload(
        domain="microsoft.com",
        position_id="1",
        job_detail={"id": 1},
        questions={},
        candidate={"email": "a@example.com"},
        answers={},
        resume_file=resume,
        include_resume_bytes=True,
    )
    assert payload["resume_upload"]["resume_file_name"] == "r.pdf"


def test_build_application_payload_without_resume() -> None:
    payload = build_application_payload(
        domain="microsoft.com",
        position_id="1",
        job_detail={"id": 1},
        questions={},
        candidate={"email": "a@example.com"},
        answers={},
        resume_file=None,
        include_resume_bytes=True,
    )
    assert "resume_file" not in payload
    assert "resume_upload" not in payload
