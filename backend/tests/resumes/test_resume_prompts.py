"""Resume-curation prompt builder and JSON parsing coverage."""

import json

import pytest

from app.resumes.prompts import SYSTEM_PROMPT, parse_curated_json, user_prompt
from app.resumes.types import ResumeCurationContext
from app.schemas.profile import EducationEntry, ProfileData, WorkExperienceEntry


def test_system_prompt_is_exposed() -> None:
    assert "JSON" in SYSTEM_PROMPT
    assert "<<<JOB_POSTING>>>" in SYSTEM_PROMPT
    assert "untrusted data" in SYSTEM_PROMPT


def test_user_prompt_includes_every_populated_field() -> None:
    ctx = ResumeCurationContext(
        job_title="Senior Engineer",
        company="ACME",
        location="Remote",
        salary="$180k",
        job_summary="strong match",
        profile=ProfileData(
            full_name="Ada",
            email="ada@example.com",
            location="Berlin",
            skills=["Python", "SQL"],
            work_experience=[
                WorkExperienceEntry(job_title="Engineer", company="Example", description="Built."),
                WorkExperienceEntry(),  # blank -> skipped
            ],
            education=[
                EducationEntry(school="MIT", degree="BSc", field_of_study="CS"),
                EducationEntry(),  # blank -> skipped
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
    assert "- Match summary: strong match" in prompt
    assert "- Name: Ada" in prompt
    assert "- Email: ada@example.com" in prompt
    assert "- Skills: Python, SQL" in prompt
    assert "- Experience: Engineer at Example" in prompt
    assert "  Description: Built." in prompt
    assert "- Education: MIT (BSc, CS)" in prompt
    assert "- Resume excerpt: Line one Line two" in prompt
    job_block = prompt.split("<<<JOB_POSTING>>>")[1].split("<<<END_JOB_POSTING>>>")[0]
    assert "Match summary: strong match" in job_block
    assert "Candidate profile:" not in job_block
    profile_block = prompt.split("<<<CANDIDATE_PROFILE>>>")[1].split("<<<END_CANDIDATE_PROFILE>>>")[
        0
    ]
    assert "Name: Ada" in profile_block
    assert "Match summary:" not in profile_block


def test_user_prompt_experience_without_description_and_education_no_detail() -> None:
    ctx = ResumeCurationContext(
        profile=ProfileData(
            work_experience=[WorkExperienceEntry(job_title="Engineer")],
            education=[EducationEntry(school="Solo School")],
        ),
    )
    prompt = user_prompt(ctx)
    assert "- Experience: Engineer at " in prompt
    assert "  Description:" not in prompt
    assert "- Education: Solo School" in prompt
    assert "(" not in prompt.split("Education: Solo School")[1].splitlines()[0]


def test_user_prompt_truncates_long_resume_excerpt() -> None:
    prompt = user_prompt(ResumeCurationContext(profile=ProfileData(resume_text="a" * 900)))
    assert "…" in prompt


def test_user_prompt_omits_empty_fields() -> None:
    prompt = user_prompt(ResumeCurationContext(profile=ProfileData()))
    assert "- Title:" not in prompt
    assert "- Name:" not in prompt
    assert "Return tailored resume placeholder JSON for this application." in prompt


def test_parse_curated_json_merges_contact_details() -> None:
    ctx = ResumeCurationContext(
        job_title="Engineer",
        company="",
        profile=ProfileData(full_name="Ada", email="ada@example.com"),
    )
    curated = parse_curated_json(json.dumps({"summary": "Great."}), ctx)
    assert curated.full_name == "Ada"
    assert curated.email == "ada@example.com"
    assert curated.company == "the hiring team"
    assert curated.summary == "Great."


def test_parse_curated_json_strips_code_fence() -> None:
    ctx = ResumeCurationContext()
    curated = parse_curated_json("```json\n" + json.dumps({"skills": "Python"}) + "\n```", ctx)
    assert curated.skills == "Python"


def test_parse_curated_json_rejects_empty_fields() -> None:
    ctx = ResumeCurationContext()
    with pytest.raises(ValueError, match="empty fields"):
        parse_curated_json(json.dumps({"summary": "", "experience": ""}), ctx)


def test_parse_curated_json_rejects_non_object() -> None:
    ctx = ResumeCurationContext()
    with pytest.raises(ValueError, match="must be a JSON object"):
        parse_curated_json(json.dumps(["not", "object"]), ctx)
