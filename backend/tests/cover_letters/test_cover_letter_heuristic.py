"""Unit tests for heuristic cover-letter generation."""

from app.cover_letters import CoverLetterContext, get_cover_letter_generator
from app.schemas.profile import ProfileData, WorkExperienceEntry


def test_heuristic_uses_template_placeholders() -> None:
    ctx = CoverLetterContext(
        job_title="Senior Engineer",
        company="ACME",
        profile=ProfileData(
            full_name="Ada Lovelace",
            cover_letter_template="Dear {company} team, I am excited about {job_title}.",
            work_experience=[
                WorkExperienceEntry(
                    job_title="Engineer",
                    company="Example Co",
                    start_month=1,
                    start_year=2020,
                )
            ],
        ),
    )
    text = get_cover_letter_generator("heuristic").generate(ctx)
    assert "Dear ACME team" in text
    assert "Senior Engineer" in text
    assert "Example Co" in text


def test_heuristic_builds_from_profile_without_template() -> None:
    ctx = CoverLetterContext(
        job_title="Platform Engineer",
        company="Globex",
        profile=ProfileData(
            full_name="Ada Lovelace",
            skills=["Python", "Kubernetes"],
        ),
    )
    text = get_cover_letter_generator("heuristic").generate(ctx)
    assert "Globex" in text
    assert "Platform Engineer" in text
    assert "Python" in text
    assert "Ada Lovelace" in text
