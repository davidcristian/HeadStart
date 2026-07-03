"""Unit tests for Google Careers apply payload builders."""

from __future__ import annotations

import pytest

from app.appliers.adapters.google_careers_detail import GoogleCareersJobDetail
from app.appliers.adapters.google_careers_payload import (
    build_application_payload,
    build_careers_profile,
    build_create_packet_args,
    build_save_packet_args,
    build_submit_packet_args,
    extract_application_id,
    extract_packet_id,
)
from app.appliers.adapters.google_careers_resume import GoogleCareersResumeAttachment
from app.schemas.profile import ProfileData, ResumeFile


def _detail(**overrides: object) -> GoogleCareersJobDetail:
    base: dict[str, object] = {
        "external_id": "123",
        "title": "Engineer",
        "apply_job_id": "TOKEN",
        "apply_url": "https://apply",
        "company": "Google",
        "company_resource": "companies/abc",
        "location_code": "US",
        "location_label": "NYC",
    }
    base.update(overrides)
    return GoogleCareersJobDetail(**base)  # type: ignore[arg-type]


def _profile(**overrides: object) -> ProfileData:
    base: dict[str, object] = {
        "full_name": "Ada Lovelace",
        "email": "ada@example.com",
    }
    base.update(overrides)
    return ProfileData(**base)


# --- build_careers_profile ---------------------------------------------------


def test_build_careers_profile_requires_full_name() -> None:
    with pytest.raises(ValueError, match="first and last name"):
        build_careers_profile(_profile(full_name="Ada"))


def test_build_careers_profile_requires_email() -> None:
    with pytest.raises(ValueError, match="email is required"):
        build_careers_profile(_profile(email=""))


def test_build_careers_profile_minimal_omits_optionals() -> None:
    payload = build_careers_profile(_profile())
    assert "phone" not in payload
    assert "location" not in payload
    assert "linkedInUrl" not in payload
    assert "resumeText" not in payload
    assert "answers" not in payload
    assert "resumeAttachment" not in payload


def test_build_careers_profile_full_fields() -> None:
    profile = _profile(
        phone="+1 555",
        location="London",
        resume_text="Engineer.",
        answers={"work_authorization": "Yes"},
        links={
            "linkedin": "https://li/ada",
            "github": "https://gh/ada",
            "website": "https://ada.dev",
        },
    )
    payload = build_careers_profile(
        profile,
        resume_attachment=GoogleCareersResumeAttachment(attachment_id="a1", filename="r.pdf"),
    )
    assert payload["phone"] == "+1 555"
    assert payload["location"] == "London"
    assert payload["linkedInUrl"] == "https://li/ada"
    assert payload["githubUrl"] == "https://gh/ada"
    assert payload["websiteUrl"] == "https://ada.dev"
    assert payload["resumeText"] == "Engineer."
    assert payload["answers"]["work_authorization"] == "Yes"
    assert payload["resumeAttachment"] == {"id": "a1", "name": "r.pdf"}


# --- build_create_packet_args ------------------------------------------------


def test_build_create_packet_args_with_optionals() -> None:
    args = build_create_packet_args(_detail())
    packet = args[0]
    assert packet["companyResource"] == "companies/abc"
    assert packet["locationCode"] == "US"


def test_build_create_packet_args_without_optionals() -> None:
    args = build_create_packet_args(_detail(company_resource="", location_code=""))
    packet = args[0]
    assert "companyResource" not in packet
    assert "locationCode" not in packet


# --- build_save_packet_args --------------------------------------------------


def test_build_save_packet_args_uses_explicit_cover_letter() -> None:
    careers_profile = build_careers_profile(_profile(answers={"q": "a"}))
    args = build_save_packet_args(
        "packet-1",
        careers_profile=careers_profile,
        cover_letter="My letter",
        job_title="Engineer",
        company="Google",
        profile=_profile(),
    )
    body = args[0]
    assert body["answers"]["coverLetter"] == "My letter"
    assert body["packetId"] == "packet-1"


def test_build_save_packet_args_renders_template() -> None:
    profile = _profile(cover_letter_template="Dear {company}, re {job_title}.")
    args = build_save_packet_args(
        "packet-2",
        careers_profile=build_careers_profile(profile),
        cover_letter=None,
        job_title="Engineer",
        company="Google",
        profile=profile,
    )
    assert "Dear Google" in args[0]["answers"]["coverLetter"]


def test_build_save_packet_args_no_letter_no_answers() -> None:
    profile = _profile(cover_letter_template="")
    args = build_save_packet_args(
        "packet-3",
        careers_profile=build_careers_profile(profile),
        cover_letter=None,
        job_title="Engineer",
        company="Google",
        profile=profile,
    )
    assert "answers" not in args[0]


def test_build_submit_packet_args() -> None:
    assert build_submit_packet_args("p") == [{"packetId": "p"}, 1, 0]


# --- build_application_payload -----------------------------------------------


def test_build_application_payload_no_cover_letter_no_resume() -> None:
    payload = build_application_payload(
        _detail(),
        _profile(),
        job_title="Engineer",
        company="Google",
    )
    assert "cover_letter" not in payload
    assert "resume_file" not in payload
    assert "resume_upload" not in payload
    assert "resume_attachment" not in payload
    assert "rpc_steps" not in payload


def test_build_application_payload_template_cover_letter() -> None:
    profile = _profile(cover_letter_template="Hi {company}")
    payload = build_application_payload(_detail(), profile, job_title="Engineer", company="Google")
    assert payload["cover_letter"] == "Hi Google"


def test_build_application_payload_explicit_cover_letter_and_resume() -> None:
    resume = ResumeFile(
        filename="resume.pdf", content_type="application/pdf", size_bytes=4, data=b"%PDF"
    )
    payload = build_application_payload(
        _detail(),
        _profile(cover_letter_template="template ignored"),
        job_title="Engineer",
        company="Google",
        cover_letter="Explicit letter",
        resume_file=resume,
    )
    assert payload["cover_letter"] == "Explicit letter"
    assert payload["resume_file"]["filename"] == "resume.pdf"
    assert payload["resume_upload"]["filename"] == "resume.pdf"


def test_build_application_payload_with_attachment_and_rpc_steps() -> None:
    payload = build_application_payload(
        _detail(),
        _profile(),
        job_title="Engineer",
        company="Google",
        include_rpc_steps=True,
        resume_attachment=GoogleCareersResumeAttachment(attachment_id="a1", filename="r.pdf"),
    )
    assert payload["resume_attachment"] == {"id": "a1", "name": "r.pdf"}
    assert payload["rpc_steps"][0]["rpc_id"] == "qvYBjf"


# --- extract_packet_id / extract_application_id ------------------------------


def test_extract_packet_id_from_dict() -> None:
    assert extract_packet_id({"packetId": "p1"}) == "p1"
    assert extract_packet_id({"applicationId": "a1"}) == "a1"
    assert extract_packet_id({"unknown": "x"}) is None


def test_extract_packet_id_from_list_head_string() -> None:
    assert extract_packet_id(["p-head"]) == "p-head"


def test_extract_packet_id_from_list_head_dict() -> None:
    assert extract_packet_id([{"id": "p2"}]) == "p2"
    assert extract_packet_id([{"nope": 1}]) is None


def test_extract_packet_id_other_types() -> None:
    assert extract_packet_id("scalar") is None
    assert extract_packet_id([]) is None
    assert extract_packet_id([0]) is None


def test_extract_application_id_from_dict() -> None:
    assert extract_application_id({"applicationId": "a1"}) == "a1"
    assert extract_application_id({"packetId": "p1"}) == "p1"
    assert extract_application_id({"nope": 1}) is None


def test_extract_application_id_from_list() -> None:
    assert extract_application_id(["app-head"]) == "app-head"
    assert extract_application_id([{"id": "a2"}]) == "a2"
    assert extract_application_id([{"nope": 1}]) is None


def test_extract_application_id_other_types() -> None:
    assert extract_application_id("scalar") is None
    assert extract_application_id([]) is None
    assert extract_application_id([0]) is None
