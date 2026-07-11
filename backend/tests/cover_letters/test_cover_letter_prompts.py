"""Cover-letter prompt builder branch coverage."""

from app.cover_letters.prompts import SYSTEM_PROMPT, user_prompt
from app.cover_letters.types import CoverLetterContext
from app.schemas.profile import (
    EducationEntry,
    ProfileData,
    ProfileLinks,
    WorkExperienceEntry,
)


def test_system_prompt_is_exposed() -> None:
    assert "cover letters" in SYSTEM_PROMPT


def test_user_prompt_includes_every_populated_field() -> None:
    ctx = CoverLetterContext(
        job_title="Senior Engineer",
        company="ACME",
        location="Remote",
        salary="$180k",
        job_summary="strong python match",
        profile=ProfileData(
            full_name="Ada Lovelace",
            location="Berlin",
            links=ProfileLinks(linkedin="li/ada", github="gh/ada"),
            skills=["Python", "SQL"],
            work_experience=[
                WorkExperienceEntry(job_title="Engineer", company="Example Co"),
                WorkExperienceEntry(job_title="Intern"),
            ],
            education=[
                EducationEntry(school="MIT", degree="BSc", field_of_study="CS"),
                EducationEntry(school="Solo School"),
            ],
            resume_text="Line one\nLine two",
        ),
    )
    prompt = user_prompt(ctx)
    assert "<<<JOB_POSTING>>>" in prompt
    assert "<<<END_JOB_POSTING>>>" in prompt
    assert "<<<CANDIDATE_PROFILE>>>" in prompt
    assert "<<<END_CANDIDATE_PROFILE>>>" in prompt
    assert "- Title: Senior Engineer" in prompt
    assert "- Company: ACME" in prompt
    assert "- Location: Remote" in prompt
    assert "- Salary: $180k" in prompt
    assert "- Match summary: strong python match" in prompt
    assert "- Name: Ada Lovelace" in prompt
    assert "- LinkedIn: li/ada" in prompt
    assert "- GitHub: gh/ada" in prompt
    assert "- Skills: Python, SQL" in prompt
    assert "- Experience: Engineer at Example Co" in prompt
    assert "- Experience: Intern" in prompt
    assert "- Education: MIT (BSc, CS)" in prompt
    assert "- Education: Solo School" in prompt
    assert "- Resume excerpt: Line one Line two" in prompt
    assert prompt.index("<<<JOB_POSTING>>>") < prompt.index("- Title: Senior Engineer")
    assert prompt.index("- Title: Senior Engineer") < prompt.index("<<<END_JOB_POSTING>>>")
    assert prompt.index("<<<CANDIDATE_PROFILE>>>") < prompt.index("- Name: Ada Lovelace")
    assert prompt.index("- Name: Ada Lovelace") < prompt.index("<<<END_CANDIDATE_PROFILE>>>")


def test_system_prompt_treats_fenced_blocks_as_data() -> None:
    assert "<<<JOB_POSTING>>>" in SYSTEM_PROMPT
    assert "untrusted data" in SYSTEM_PROMPT


def test_user_prompt_truncates_long_resume_excerpt() -> None:
    ctx = CoverLetterContext(profile=ProfileData(resume_text="a" * 700))
    prompt = user_prompt(ctx)
    assert "…" in prompt


def test_user_prompt_skips_blank_experience_and_education_entries() -> None:
    ctx = CoverLetterContext(
        profile=ProfileData(
            work_experience=[WorkExperienceEntry()],
            education=[EducationEntry()],
        ),
    )
    prompt = user_prompt(ctx)
    assert "- Experience:" not in prompt
    assert "- Education:" not in prompt


def test_user_prompt_omits_empty_fields() -> None:
    prompt = user_prompt(CoverLetterContext())
    assert "- Title:" not in prompt
    assert "- Name:" not in prompt
    assert "- Skills:" not in prompt
    assert "Write a tailored cover letter for this application." in prompt
