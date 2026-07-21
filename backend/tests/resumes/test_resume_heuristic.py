"""Tests for heuristic resume curation."""

from app.resumes.adapters.heuristic import HeuristicResumeCurator
from app.resumes.base import get_resume_curator
from app.resumes.fields import heuristic_fields
from app.resumes.types import ResumeCurationContext
from app.schemas.profile import EducationEntry, ProfileData, WorkExperienceEntry


def test_registry_resolves_and_curates_via_heuristic() -> None:
    curator = get_resume_curator("heuristic")
    assert isinstance(curator, HeuristicResumeCurator)
    fields = curator.curate(ResumeCurationContext(job_title="Engineer", company="ACME"))
    assert fields.job_title == "Engineer"
    assert fields.company == "ACME"


def test_heuristic_fields_include_job_context() -> None:
    ctx = ResumeCurationContext(
        job_title="Senior Engineer",
        company="ACME",
        profile=ProfileData(
            full_name="Ada Lovelace",
            skills=["Python", "SQL"],
            work_experience=[
                WorkExperienceEntry(
                    job_title="Engineer",
                    company="Example Corp",
                    start_year=2020,
                    start_month=1,
                    description="Built APIs.",
                )
            ],
        ),
    )
    fields = heuristic_fields(ctx)
    assert fields.full_name == "Ada Lovelace"
    assert fields.job_title == "Senior Engineer"
    assert fields.company == "ACME"
    assert "Python" in fields.skills
    assert r"\item" in fields.experience
    assert "Example Corp" in fields.experience


def test_heuristic_fields_format_education_and_current_role() -> None:
    ctx = ResumeCurationContext(
        job_title="Staff Engineer",
        company="ACME",
        profile=ProfileData(
            full_name="Ada Lovelace",
            skills=["Python"] + [f"skill-{i}" for i in range(25)],
            work_experience=[
                WorkExperienceEntry(
                    job_title="Engineer",
                    company="Example Corp",
                    start_year=2022,
                    start_month=3,
                    is_current=True,
                    description="Led platform work.",
                )
            ],
            education=[
                EducationEntry(
                    school="Example University",
                    degree="BSc",
                    field_of_study="Computer Science",
                    start_year=2016,
                    end_year=2020,
                )
            ],
        ),
    )
    fields = heuristic_fields(ctx)
    assert "Mar 2022 to Present" in fields.experience
    assert "Example University" in fields.education
    assert "BSc" in fields.education
    assert fields.skills.count(",") == 19
