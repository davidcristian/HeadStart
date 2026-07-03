"""Tests for shared structured profile helpers."""

from app.appliers.structured_profile import (
    applicable_skills,
    applicable_work_experience,
    build_profile_supplement,
    format_education_entry,
    format_work_experience_entry,
)
from app.schemas.profile import EducationEntry, ProfileData, WorkExperienceEntry


def test_applicable_work_experience_requires_title_company_and_start_date() -> None:
    profile = ProfileData(
        work_experience=[
            WorkExperienceEntry(
                job_title="Engineer",
                company="ACME",
                start_month=3,
                start_year=2020,
            ),
            WorkExperienceEntry(job_title="Intern", company="ACME"),
        ]
    )
    assert len(applicable_work_experience(profile)) == 1


def test_build_profile_supplement_formats_sections() -> None:
    profile = ProfileData(
        work_experience=[
            WorkExperienceEntry(
                job_title="Engineer",
                company="ACME",
                location="Remote",
                start_month=3,
                start_year=2020,
                end_month=6,
                end_year=2023,
            )
        ],
        education=[
            EducationEntry(
                school="Example University",
                degree="Bachelor of Science",
                field_of_study="Computer Science",
                start_year=2016,
                end_year=2020,
                gpa="3.8",
            )
        ],
        skills=["Python", "SQL"],
    )
    supplement = build_profile_supplement(profile)
    assert supplement is not None
    assert "Work experience:" in supplement
    assert "Engineer at ACME (Remote)" in supplement
    assert "Education:" in supplement
    assert "Example University" in supplement
    assert "Skills: Python, SQL" in supplement


def test_format_helpers_handle_current_role_and_plain_school() -> None:
    current = format_work_experience_entry(
        WorkExperienceEntry(
            job_title="Lead",
            company="ACME",
            start_month=1,
            start_year=2024,
            is_current=True,
        )
    )
    assert "Present" in current

    plain_school = format_education_entry(EducationEntry(school="Example University"))
    assert plain_school == "- Example University"

    assert applicable_skills(ProfileData(skills=["  ", "Go"])) == ["Go"]


def test_format_work_experience_entry_appends_description() -> None:
    line = format_work_experience_entry(
        WorkExperienceEntry(
            job_title="Engineer",
            company="ACME",
            start_month=3,
            start_year=2020,
            description="Shipped features.",
        )
    )
    assert "\n  Shipped features." in line


def test_format_work_experience_entry_year_only_period() -> None:
    line = format_work_experience_entry(
        WorkExperienceEntry(
            job_title="Engineer",
            company="ACME",
            start_year=2020,
        )
    )
    assert "(2020)" in line


def test_build_profile_supplement_returns_none_when_empty() -> None:
    assert build_profile_supplement(ProfileData()) is None
