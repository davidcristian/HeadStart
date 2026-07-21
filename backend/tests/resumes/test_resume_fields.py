"""Branch coverage for resume field formatting."""

from app.resumes.fields import heuristic_fields
from app.resumes.types import ResumeCurationContext
from app.schemas.profile import EducationEntry, ProfileData, WorkExperienceEntry


def _fields(profile: ProfileData, **ctx: object):
    return heuristic_fields(ResumeCurationContext(profile=profile, **ctx))  # type: ignore[arg-type]


def test_summary_uses_resume_text_excerpt_with_truncation() -> None:
    fields = _fields(ProfileData(resume_text="a" * 600 + "\nmore"), job_title="Eng", company="ACME")
    assert fields.summary.startswith("Experienced candidate targeting the Eng role at ACME.")
    assert "…" in fields.summary


def test_summary_defaults_include_job_summary() -> None:
    fields = _fields(ProfileData(), job_title="Eng", company="ACME", job_summary="great fit.")
    assert "Experienced professional interested in the Eng position at ACME." in fields.summary
    assert "great fit." in fields.summary


def test_summary_without_resume_or_job_summary() -> None:
    fields = _fields(ProfileData(), job_title="Eng", company="ACME")
    assert fields.summary.endswith("at ACME.")


def test_experience_skips_blank_entries_and_falls_back_to_resume() -> None:
    fields = _fields(
        ProfileData(
            work_experience=[WorkExperienceEntry()],
            resume_text="First line of resume\nsecond",
        )
    )
    assert fields.experience == r"\item First line of resume"


def test_experience_falls_back_to_placeholder_without_any_data() -> None:
    fields = _fields(ProfileData())
    assert "Relevant professional experience available upon request" in fields.experience


def test_experience_item_uses_company_only_and_period_and_description() -> None:
    fields = _fields(
        ProfileData(
            work_experience=[
                WorkExperienceEntry(
                    company="ACME",
                    start_year=2019,
                    end_year=2021,
                    description="- Did things\n* And more",
                )
            ]
        )
    )
    assert r"\textbf{ACME}" in fields.experience
    assert "(2019 to 2021)" in fields.experience
    assert "Did things" in fields.experience
    assert "And more" in fields.experience
    # Pins the exact tail: the description hangs off the dates on a full stop, and the
    # bullet-marker stripping leaves the spacing the literal shows.
    assert fields.experience == r"\item \textbf{ACME} (2019 to 2021).  Did things  And more"


def test_experience_item_escapes_latex_special_chars_in_free_text() -> None:
    # \item / \textbf scaffolding stays raw, but user free text is escaped so it
    # cannot break the compile once the renderer stops escaping this field.
    fields = _fields(
        ProfileData(
            work_experience=[
                WorkExperienceEntry(company="AT&T", description="Cut costs 50% via C#")
            ]
        )
    )
    assert r"\item \textbf{AT\&T}" in fields.experience
    assert r"50\%" in fields.experience
    assert r"C\#" in fields.experience


def test_experience_fallback_escapes_resume_text() -> None:
    fields = _fields(ProfileData(resume_text="Saved 20% & shipped"))
    assert fields.experience == r"\item Saved 20\% \& shipped"


def test_experience_item_without_period_or_description() -> None:
    fields = _fields(ProfileData(work_experience=[WorkExperienceEntry(job_title="Engineer")]))
    assert r"\item \textbf{Engineer}" in fields.experience
    assert "(" not in fields.experience
    # Exact match: with no dates and no description, neither the "(dates)" suffix nor
    # the ". description" tail may be appended.
    assert fields.experience == r"\item \textbf{Engineer}"


def test_period_year_only_when_month_missing() -> None:
    fields = _fields(
        ProfileData(work_experience=[WorkExperienceEntry(job_title="X", start_year=2018)])
    )
    assert "(2018)" in fields.experience


def test_education_skips_blank_and_formats_end_year_only() -> None:
    fields = _fields(
        ProfileData(
            education=[
                EducationEntry(),  # blank, skipped
                EducationEntry(school="MIT", degree="BSc", end_year=2020),
            ]
        )
    )
    assert "BSc at MIT (2020)" in fields.education


def test_education_detail_without_years() -> None:
    fields = _fields(ProfileData(education=[EducationEntry(school="MIT", degree="BSc")]))
    assert "BSc at MIT" in fields.education
    assert "(" not in fields.education


def test_education_placeholder_without_entries() -> None:
    fields = _fields(ProfileData())
    assert fields.education == "Education details available upon request."


def test_skills_empty_returns_blank() -> None:
    fields = _fields(ProfileData(skills=["   "]))
    assert fields.skills == ""
