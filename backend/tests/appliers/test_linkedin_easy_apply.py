"""Unit tests for LinkedIn Easy Apply payload builders."""

from __future__ import annotations

import pytest

from app.appliers.adapters.linkedin_detail import LinkedInJobDetail
from app.appliers.adapters.linkedin_easy_apply import (
    build_easy_apply_payload,
    build_submit_body,
)
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile


def _detail() -> LinkedInJobDetail:
    return LinkedInJobDetail(
        job_id="4434410881",
        title="Quantitative Trader",
        company="Example Co",
        reference_id="ref-1",
        tracking_id="trk-1",
        easy_apply=True,
        offsite_apply=False,
        external_apply_url=None,
        expired=False,
    )


def _profile(**overrides: object) -> ProfileData:
    base: dict[str, object] = {
        "full_name": "Ada Lovelace",
        "email": "ada@example.com",
        "phone": "+1 555 0100",
        "location": "Remote",
        "resume_text": "Experienced engineer.",
        "cover_letter_template": "Dear {company}, excited about {job_title}.",
    }
    base.update(overrides)
    return ProfileData(**base)


def _form_root(elements: list[dict[str, object]]) -> dict[str, object]:
    return {
        "questionGroupings": [{"formSection": {"formElementGroups": [{"formElements": elements}]}}]
    }


def _text_el(urn: str, title: str) -> dict[str, object]:
    return {
        "entityUrn": urn,
        "title": {"text": title},
        "formComponentResolutionResult": {"singleLineTextFormComponent": {}},
    }


def test_build_easy_apply_payload_full_fields() -> None:
    payload = build_easy_apply_payload(
        _detail(),
        _profile(),
        company="Example Co",
        job_title="Quantitative Trader",
        cover_letter=None,
        resume_file=None,
    )
    assert payload["applicant"]["phone"] == "+1 555 0100"
    assert payload["applicant"]["location"] == "Remote"
    assert "Example Co" in payload["coverLetter"]
    assert payload["resumeText"] == "Experienced engineer."


def test_build_easy_apply_payload_minimal_fields_skipped() -> None:
    profile = _profile(
        phone="",
        location="",
        resume_text="",
        cover_letter_template="",
    )
    payload = build_easy_apply_payload(
        _detail(),
        profile,
        company="Example Co",
        job_title="Trader",
        cover_letter=None,
        resume_file=None,
    )
    assert "phone" not in payload["applicant"]
    assert "location" not in payload["applicant"]
    assert "coverLetter" not in payload
    assert "resumeText" not in payload


def test_build_easy_apply_payload_resume_from_apply_profile() -> None:
    resume = ResumeFile(
        filename="resume.pdf", content_type="application/pdf", size_bytes=4, data=b"%PDF"
    )
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)
    payload = build_easy_apply_payload(
        _detail(),
        profile,
        company="Example Co",
        job_title="Trader",
        cover_letter=None,
        resume_file=None,
    )
    assert payload["resume_file"]["filename"] == "resume.pdf"


def test_build_easy_apply_payload_requires_name_and_email() -> None:
    with pytest.raises(ValueError, match="full_name and email"):
        build_easy_apply_payload(
            _detail(),
            _profile(email=""),
            company="Example Co",
            job_title="Trader",
            cover_letter=None,
            resume_file=None,
        )


def test_build_easy_apply_payload_answers_included() -> None:
    profile = _profile(answers={"work_authorization": "US citizen", "blank": ""})
    payload = build_easy_apply_payload(
        _detail(),
        profile,
        company="Example Co",
        job_title="Trader",
        cover_letter=None,
        resume_file=None,
    )
    assert payload["answers"]["work_authorization"] == "US citizen"
    assert "blank" not in payload["answers"]


def test_build_easy_apply_payload_with_form_and_missing() -> None:
    form_root = _form_root(
        [
            {
                "required": True,
                "title": {"text": "First name"},
                "entityUrn": "urn:1",
                "formComponentResolutionResult": {"singleLineTextFormComponent": {}},
            },
            {
                "required": True,
                "title": {"text": "Salary expectation"},
                "entityUrn": "urn:2",
                "formComponentResolutionResult": {"singleLineTextFormComponent": {}},
            },
        ]
    )
    payload = build_easy_apply_payload(
        _detail(),
        _profile(),
        company="Example Co",
        job_title="Trader",
        cover_letter="A cover letter",
        resume_file=None,
        form_payload=form_root,
    )
    assert payload["form"] is form_root
    assert any(r["formElementUrn"] == "urn:1" for r in payload["responses"])
    assert payload["missing_required_fields"] == ["Salary expectation"]


def test_build_submit_body_raises_without_responses() -> None:
    with pytest.raises(ValueError, match="required Easy Apply questions"):
        build_submit_body({"responses": []})


def test_build_submit_body_uses_reference_and_uploads() -> None:
    body = build_submit_body(
        {
            "responses": [{"formElementUrn": "urn:1"}],
            "referenceId": "REF-9",
            "trackingId": "TRK-9",
            "fileUploadResponses": [{"formElementUrn": "urn:file"}],
        }
    )
    assert body["referenceId"] == "REF-9"
    assert body["trackingCode"] == "TRK-9"
    assert body["fileUploadResponses"] == [{"formElementUrn": "urn:file"}]


def test_build_submit_body_generates_reference_when_missing() -> None:
    body = build_submit_body({"responses": [{"formElementUrn": "urn:1"}]})
    assert body["referenceId"].startswith("INITIAL_PAGE_LOAD::::")
    assert body["trackingCode"] == "TRK_INITIAL_PAGE_LOAD"
    assert body["fileUploadResponses"] == []


def test_build_easy_apply_payload_form_without_missing() -> None:
    form_root = _form_root([_text_el("urn:email", "Email address")])
    payload = build_easy_apply_payload(
        _detail(),
        _profile(),
        company="Example Co",
        job_title="Trader",
        cover_letter=None,
        resume_file=None,
        form_payload=form_root,
    )
    assert "missing_required_fields" not in payload
    assert len(payload["responses"]) == 1
