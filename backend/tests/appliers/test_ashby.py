"""Tests for the Ashby apply adapter (payload building and helpers)."""

import json

from app.appliers.adapters.ashby import (
    build_application_payload,
    resolve_board,
)
from app.appliers.adapters.ashby_response import (
    extract_application_id,
    extract_blocked_message,
    extract_error_message,
)
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile
from tests.conftest import load_fixture


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="London, UK",
        resume_text="Experienced engineer.",
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        answers={"custom_question_path": "Yes"},
    )


def _resume() -> ResumeFile:
    return ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )


def test_resolve_board_from_config_or_url() -> None:
    assert resolve_board({"board": "acme"}, "") == "acme"
    assert (
        resolve_board(
            {},
            "https://jobs.ashbyhq.com/acme/7458d4e9-da2e-47bd-98cb-adfda43d42b2/application",
        )
        == "acme"
    )
    assert resolve_board({}, "https://example.com/jobs/1") is None


def test_build_application_payload_maps_profile_fields() -> None:
    built = build_application_payload(
        "7458d4e9-da2e-47bd-98cb-adfda43d42b2",
        _profile(),
        job_title="Senior Engineer",
        company="ACME",
        config={
            "phone_path": "phone_field",
            "location_path": "location_field",
            "cover_letter_path": "cover_letter_field",
        },
    )
    payload = built["payload"]
    submissions = payload["applicationForm"]["fieldSubmissions"]
    by_path = {item["path"]: item["value"] for item in submissions}
    assert payload["jobPostingId"] == "7458d4e9-da2e-47bd-98cb-adfda43d42b2"
    assert by_path["_systemfield_name"] == "Ada Lovelace"
    assert by_path["_systemfield_email"] == "ada@example.com"
    assert by_path["phone_field"] == "+1 555 0100"
    assert by_path["location_field"] == "London, UK"
    assert "ACME" in by_path["cover_letter_field"]
    assert "Resume:" in by_path["cover_letter_field"]
    assert by_path["custom_question_path"] == "Yes"


def test_build_application_payload_uses_cover_letter_override() -> None:
    built = build_application_payload(
        "7458d4e9-da2e-47bd-98cb-adfda43d42b2",
        _profile(),
        job_title="Senior Engineer",
        company="ACME",
        config={"cover_letter_path": "cover_letter_field"},
        cover_letter="Custom letter for ACME",
    )
    payload = built["payload"]
    submissions = payload["applicationForm"]["fieldSubmissions"]
    by_path = {item["path"]: item["value"] for item in submissions}
    assert by_path["cover_letter_field"] == (
        "Custom letter for ACME\n\nResume:\nExperienced engineer."
    )


def test_build_application_payload_includes_resume_multipart() -> None:
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)
    built = build_application_payload(
        "7458d4e9-da2e-47bd-98cb-adfda43d42b2",
        profile,
        job_title="Senior Engineer",
        company="ACME",
        config={},
    )
    payload = built["payload"]
    submissions = payload["applicationForm"]["fieldSubmissions"]
    by_path = {item["path"]: item["value"] for item in submissions}
    assert by_path["_systemfield_resume"] == "resume_1"
    assert built["multipart"]["files"]["resume_1"][0] == "resume.pdf"
    assert "Resume:" not in str(payload)


def test_build_application_payload_requires_name_and_email() -> None:
    try:
        build_application_payload(
            "job-1",
            ProfileData(full_name="", email="ada@example.com"),
            job_title="Role",
            company="ACME",
            config={},
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "full_name" in str(exc)


def test_extract_helpers() -> None:
    success = load_fixture("ashby_apply_success.json")
    assert extract_application_id(json.loads(success)) == "f47ac10b-58cc-4372-a567-0e02b2c3d479"
    assert extract_blocked_message(json.loads(success)) is None
    assert extract_error_message({"success": False, "errors": ["invalid_input"]}) == "invalid_input"
    assert (
        extract_blocked_message(
            {
                "success": True,
                "results": {
                    "formMessages": {
                        "blocked": True,
                        "blockMessageForCandidateHtml": "Too many applications",
                    }
                },
            }
        )
        == "Too many applications"
    )


def test_build_application_payload_requires_email() -> None:
    try:
        build_application_payload(
            "job-1",
            ProfileData(full_name="Ada", email=""),
            job_title="Role",
            company="ACME",
            config={},
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "email" in str(exc)


def test_build_application_payload_skips_blank_or_used_answers() -> None:
    profile = _profile()
    profile.answers = {
        "_systemfield_name": "override attempt",
        "blank_answer": "",
        "extra_answer": "Yes",
    }
    built = build_application_payload(
        "job-1",
        profile,
        job_title="Role",
        company="ACME",
        config={},
    )
    submissions = built["payload"]["applicationForm"]["fieldSubmissions"]
    name_entries = [item for item in submissions if item["path"] == "_systemfield_name"]
    assert name_entries == [{"path": "_systemfield_name", "value": "Ada Lovelace"}]
    assert not any(item["path"] == "blank_answer" for item in submissions)
    assert any(item["path"] == "extra_answer" for item in submissions)


def test_resolve_api_key_falls_back_to_config_when_session_blank() -> None:
    from app.appliers.adapters.ashby import resolve_api_key

    key = resolve_api_key(
        {"session": {"ashby_api_key": ""}, "cookies": {}, "headers": {}},
        {"ashby_api_key": "config-key"},
    )
    assert key == "config-key"


def test_resolve_api_key_none_when_nothing_configured() -> None:
    from app.appliers.adapters.ashby import resolve_api_key

    assert resolve_api_key(None, {}) is None


def test_build_application_payload_disallows_unpublished_in_json_and_multipart() -> None:
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=_resume())
    built = build_application_payload(
        "job-1",
        profile,
        job_title="Role",
        company="ACME",
        config={"allow_unpublished_job_posting": False},
    )
    assert built["payload"]["allowSubmissionForUnpublishedJobPosting"] is False
    assert built["multipart"]["data"]["allowSubmissionForUnpublishedJobPosting"] == "false"
