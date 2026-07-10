"""Tests for the Apple Careers apply payload builders."""

import pytest

from app.appliers.adapters.apple_careers_detail import AppleCareersJobDetail
from app.appliers.adapters.apple_careers_payload import (
    build_application_payload,
    build_apply_body,
    build_contact,
    build_education_degrees,
    build_employments,
    build_links,
    build_resume_ref,
    build_roles,
    build_talent,
    resolve_post_locations,
)
from app.schemas.profile import ProfileData, ResumeFile


def _detail(**overrides: object) -> AppleCareersJobDetail:
    base: dict[str, object] = {
        "position_id": "REQ-1",
        "job_number": "1001",
        "title": "Engineer",
        "job_type": "REQ",
        "pipeline_type": "SWE",
        "role_location_selection": False,
        "managed_pipeline_role": False,
        "transformed_posting_title": "engineer",
        "locale": "en-us",
        "locations": (),
    }
    base.update(overrides)
    return AppleCareersJobDetail(**base)  # type: ignore[arg-type]


def test_build_contact_requires_first_and_last_name() -> None:
    with pytest.raises(ValueError, match="first and last name"):
        build_contact(ProfileData(full_name="Madonna", email="a@b.com"))


def test_build_contact_requires_email() -> None:
    with pytest.raises(ValueError, match="email is required"):
        build_contact(ProfileData(full_name="Ada Lovelace", email="   "))


def test_build_contact_omits_phone_when_blank() -> None:
    contact = build_contact(ProfileData(full_name="Ada Lovelace", email="a@b.com", phone="  "))
    assert "preferredPhone" not in contact


def test_build_links_includes_all_present_links() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        links={
            "linkedin": "https://linkedin.com/in/ada",
            "github": "https://github.com/ada",
            "website": "https://ada.dev",
        },
    )
    links = build_links(profile)
    assert links == [
        {"type": "linkedin", "url": "https://linkedin.com/in/ada"},
        {"type": "github", "url": "https://github.com/ada"},
        {"type": "website", "url": "https://ada.dev"},
    ]


def test_build_links_empty_when_all_blank() -> None:
    assert build_links(ProfileData(full_name="Ada Lovelace")) == []


def test_build_employments_maps_all_fields() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        work_experience=[
            {
                "job_title": "Engineer",
                "company": "Acme",
                "location": "Remote",
                "start_year": 2018,
                "start_month": 1,
                "end_year": 2020,
                "end_month": 12,
                "is_current": False,
                "description": "Built things.",
            }
        ],
    )
    [entry] = build_employments(profile)
    assert entry == {
        "jobTitle": "Engineer",
        "employerName": "Acme",
        "isCurrent": False,
        "location": "Remote",
        "startYear": 2018,
        "startMonth": 1,
        "endYear": 2020,
        "endMonth": 12,
        "description": "Built things.",
    }


def test_build_employments_skips_blank_rows_and_optional_fields() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        work_experience=[
            {"job_title": "  ", "company": "  "},
            {"job_title": "Engineer", "company": "Acme"},
        ],
    )
    entries = build_employments(profile)
    assert len(entries) == 1
    assert entries[0] == {"jobTitle": "Engineer", "employerName": "Acme", "isCurrent": False}


def test_build_education_degrees_maps_all_fields() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        education=[
            {
                "school": "MIT",
                "degree": "BS",
                "field_of_study": "CS",
                "start_year": 2014,
                "end_year": 2018,
                "gpa": "4.0",
            }
        ],
    )
    [entry] = build_education_degrees(profile)
    assert entry == {
        "schoolName": "MIT",
        "degreeName": "BS",
        "fieldOfStudy": "CS",
        "startYear": 2014,
        "endYear": 2018,
        "gpa": "4.0",
    }


def test_build_education_degrees_skips_schoolless_and_optional_fields() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        education=[
            {"school": "  ", "degree": "BS"},
            {"school": "MIT"},
        ],
    )
    entries = build_education_degrees(profile)
    assert entries == [{"schoolName": "MIT"}]


def test_build_roles_retail_role_location_selection() -> None:
    detail = _detail(role_location_selection=True)
    roles = build_roles(detail, talent_id="t1", post_locations=[{"id": "store-1"}])
    assert roles["resubmitted"] is True
    assert roles["roleLocation"] is True
    assert roles["storeLocations"] == [{"id": "store-1"}]
    assert "postLocations" not in roles


def test_build_roles_retail_without_locations_sets_false() -> None:
    detail = _detail(role_location_selection=True)
    roles = build_roles(detail, talent_id="t1", post_locations=[])
    assert roles["roleLocation"] is False


def test_build_talent_includes_all_sections() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        links={"linkedin": "https://linkedin.com/in/ada"},
        work_experience=[{"job_title": "Engineer", "company": "Acme"}],
        education=[{"school": "MIT"}],
        skills=["Python", "  "],
        languages=[
            {"language": "English", "proficiency": "Native", "is_native": True},
            {"language": "  ", "proficiency": "x"},
        ],
    )
    talent = build_talent(profile, talent_id="t1", contact={"firstName": "Ada"})
    assert talent["links"] == [{"type": "linkedin", "url": "https://linkedin.com/in/ada"}]
    assert talent["employmentHasAtLeastOneJob"] is True
    assert "educationDegrees" in talent
    assert talent["skills"] == ["Python"]
    assert talent["languages"] == [
        {"language": "English", "proficiency": "Native", "isNative": True}
    ]


def test_build_talent_omits_empty_sections() -> None:
    talent = build_talent(
        ProfileData(full_name="Ada Lovelace"), talent_id="t1", contact={"firstName": "Ada"}
    )
    for key in ("links", "employments", "educationDegrees", "skills", "languages"):
        assert key not in talent


def test_build_apply_body_adds_board_id_for_managed_role() -> None:
    detail = _detail(managed_pipeline_role=True)
    body = build_apply_body(detail=detail, talent_id="t1", talent={}, roles={})
    assert body["boardId"] == detail.position_id
    assert "questionnaireAnswers" not in body


def test_build_apply_body_includes_questionnaire_answers() -> None:
    detail = _detail()
    answers = {
        "id": "q-1",
        "questionnaireId": "q-1",
        "questionCategory": "APPLICATION",
        "answers": {"work_authorization": "Yes"},
        "reset": False,
    }
    body = build_apply_body(
        detail=detail,
        talent_id="t1",
        talent={},
        roles={},
        questionnaire_answers=answers,
    )
    assert body["questionnaireAnswers"] == answers


def test_resolve_post_locations_prefers_configured_dicts() -> None:
    detail = _detail(locations=({"id": "detail-loc"},))
    config = {"post_locations": [{"id": "cfg-1"}, "not-a-dict"]}
    assert resolve_post_locations(detail, config, ProfileData()) == [{"id": "cfg-1"}]


def test_resolve_post_locations_falls_back_to_detail_then_empty() -> None:
    detail = _detail(locations=({"id": "detail-loc"},))
    assert resolve_post_locations(detail, {}, ProfileData()) == [{"id": "detail-loc"}]
    assert resolve_post_locations(_detail(), {}, ProfileData()) == []


def test_build_application_payload_without_talent_id_or_resume() -> None:
    detail = _detail()
    payload = build_application_payload(
        detail=detail,
        profile=ProfileData(full_name="Ada Lovelace", email="a@b.com"),
        talent_id=None,
        post_locations=[],
        contact={},
        talent={},
        roles={},
        apply_body={},
        resume_file=None,
    )
    assert payload["apply_job"]["url"] is None
    assert "resume_file" not in payload
    assert "resume_upload" not in payload


def test_build_application_payload_resume_without_talent_id_omits_upload() -> None:
    resume = ResumeFile(
        filename="resume.pdf", content_type="application/pdf", size_bytes=4, data=b"%PDF"
    )
    payload = build_application_payload(
        detail=_detail(),
        profile=ProfileData(full_name="Ada Lovelace", email="a@b.com"),
        talent_id=None,
        post_locations=[],
        contact={},
        talent={},
        roles={},
        apply_body={},
        resume_file=resume,
    )
    assert payload["resume_file"]["filename"] == "resume.pdf"
    assert "resume_upload" not in payload


def test_build_resume_ref_variants() -> None:
    assert build_resume_ref("not-a-dict") is None
    assert build_resume_ref({"noFileId": "x"}) is None
    assert build_resume_ref({"id": "file-1", "pdfFileId": "pdf-1"}) == {
        "fileId": "file-1",
        "pdfFileId": "pdf-1",
    }
