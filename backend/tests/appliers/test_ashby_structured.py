"""Tests for Ashby structured profile mapping."""

from app.appliers.adapters.ashby import build_application_payload
from app.appliers.adapters.ashby_structured import (
    build_education_history,
    build_skills_value,
    build_work_history_text,
)
from app.schemas.profile import EducationEntry, ProfileData, WorkExperienceEntry


def test_build_application_payload_maps_structured_profile_paths() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        work_experience=[
            WorkExperienceEntry(
                job_title="Engineer",
                company="ACME",
                start_month=3,
                start_year=2020,
            )
        ],
        education=[
            EducationEntry(
                school="Example University",
                degree="Bachelor of Science",
                field_of_study="Computer Science",
                start_year=2016,
                end_year=2020,
            )
        ],
        skills=["Python", "SQL"],
    )
    built = build_application_payload(
        "7458d4e9-da2e-47bd-98cb-adfda43d42b2",
        profile,
        job_title="Senior Engineer",
        company="ACME",
        config={
            "education_history_path": "education_history",
            "work_history_path": "work_history",
            "skills_path": "skills_field",
        },
    )
    submissions = built["payload"]["applicationForm"]["fieldSubmissions"]
    by_path = {item["path"]: item["value"] for item in submissions}
    assert by_path["education_history"][0]["schoolName"] == "Example University"
    assert by_path["education_history"][0]["major"] == "Computer Science"
    assert "Engineer at ACME" in by_path["work_history"]
    assert by_path["skills_field"] == ["Python", "SQL"]


def test_build_application_payload_maps_skills_as_string_when_configured() -> None:
    built = build_application_payload(
        "job-1",
        ProfileData(
            full_name="Ada Lovelace",
            email="ada@example.com",
            skills=["Python", "SQL"],
        ),
        job_title="Role",
        company="ACME",
        config={"skills_path": "skills_field", "skills_value_format": "string"},
    )
    submissions = built["payload"]["applicationForm"]["fieldSubmissions"]
    by_path = {item["path"]: item["value"] for item in submissions}
    assert by_path["skills_field"] == "Python, SQL"


def test_structured_paths_skipped_when_no_matching_profile_data() -> None:
    # Paths are configured but the profile has no education/work/skills, so each
    # builder returns empty and no submission is appended.
    built = build_application_payload(
        "job-1",
        ProfileData(full_name="Ada Lovelace", email="ada@example.com"),
        job_title="Role",
        company="ACME",
        config={
            "education_history_path": "education_history",
            "work_history_path": "work_history",
            "skills_path": "skills_field",
        },
    )
    submissions = built["payload"]["applicationForm"]["fieldSubmissions"]
    paths = {item["path"] for item in submissions}
    assert "education_history" not in paths
    assert "work_history" not in paths
    assert "skills_field" not in paths


def test_build_education_history_omits_optional_fields() -> None:
    rows = build_education_history(
        ProfileData(education=[EducationEntry(school="Example University")])
    )
    assert rows == [{"schoolName": "Example University"}]


def test_build_work_history_text_none_when_empty() -> None:
    assert build_work_history_text(ProfileData()) is None


def test_build_skills_value_none_when_empty() -> None:
    assert build_skills_value(ProfileData(), as_string=False) is None
    assert build_skills_value(ProfileData(), as_string=True) is None
