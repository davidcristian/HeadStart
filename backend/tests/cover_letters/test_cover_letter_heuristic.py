"""Unit tests for heuristic cover-letter generation."""

from app.cover_letters import CoverLetterContext, get_cover_letter_generator
from app.cover_letters.adapters.heuristic import HeuristicCoverLetterGenerator
from app.schemas.profile import ProfileData, WorkExperienceEntry


def test_registry_resolves_heuristic() -> None:
    assert isinstance(get_cover_letter_generator("heuristic"), HeuristicCoverLetterGenerator)


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


def test_heuristic_defaults_company_and_role_and_includes_summary() -> None:
    # Empty company/job title exercise the fallback defaults, and a job_summary
    # exercises the "stood out" paragraph. A single skill exercises the
    # single-skill branch in _skills_line.
    ctx = CoverLetterContext(
        job_title="",
        company="",
        job_summary="it matches my backend background.",
        profile=ProfileData(skills=["Python"]),
    )
    text = get_cover_letter_generator("heuristic").generate(ctx)
    assert "the hiring team" in text
    assert "this role" in text
    assert "This opportunity stood out to me because" in text
    assert "it matches my backend background." in text
    assert "Key strengths I would bring include Python." in text
    assert text.endswith("Sincerely")


def test_heuristic_experience_line_uses_title_only() -> None:
    ctx = CoverLetterContext(
        job_title="Engineer",
        company="ACME",
        profile=ProfileData(
            work_experience=[WorkExperienceEntry(job_title="Staff Engineer")],
        ),
    )
    text = get_cover_letter_generator("heuristic").generate(ctx)
    assert "My background as Staff Engineer aligns well" in text


def test_heuristic_experience_line_falls_back_to_resume_excerpt() -> None:
    long_line = "x" * 250
    ctx = CoverLetterContext(
        job_title="Engineer",
        company="ACME",
        profile=ProfileData(resume_text=long_line + "\nsecond line"),
    )
    text = get_cover_letter_generator("heuristic").generate(ctx)
    assert "My background includes:" in text
    assert "…" in text


def test_heuristic_experience_skips_blank_entry_and_keeps_short_excerpt() -> None:
    # First entry has neither title nor company (loop continues), then a short
    # resume excerpt is used verbatim without truncation.
    ctx = CoverLetterContext(
        job_title="Engineer",
        company="ACME",
        profile=ProfileData(
            work_experience=[WorkExperienceEntry()],
            resume_text="Short summary line",
        ),
    )
    text = get_cover_letter_generator("heuristic").generate(ctx)
    assert "My background includes: Short summary line" in text
    assert "…" not in text
