"""Tests for heuristic resume curation."""

from app.resumes.fields import heuristic_fields
from app.resumes.types import ResumeCurationContext
from app.schemas.profile import ProfileData, WorkExperienceEntry


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
