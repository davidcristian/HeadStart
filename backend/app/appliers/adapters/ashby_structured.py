"""Ashby structured profile field builders for applicationForm.submit."""

from __future__ import annotations

from typing import Any

from app.appliers.structured_profile import (
    applicable_education,
    applicable_skills,
    applicable_work_experience,
    format_work_experience_entry,
)
from app.schemas.profile import ProfileData


def append_structured_profile_submissions(
    submissions: list[dict[str, Any]],
    used_paths: set[str],
    profile: ProfileData,
    config: dict[str, Any],
) -> None:
    """Add configured education, work-history, and skills field submissions."""
    education_history_path = config.get("education_history_path")
    if education_history_path:
        education_history = build_education_history(profile)
        if education_history:
            path = str(education_history_path)
            submissions.append({"path": path, "value": education_history})
            used_paths.add(path)

    work_history_path = config.get("work_history_path")
    if work_history_path:
        work_history = build_work_history_text(profile)
        if work_history:
            path = str(work_history_path)
            submissions.append({"path": path, "value": work_history})
            used_paths.add(path)

    skills_path = config.get("skills_path")
    if skills_path:
        skills_value = build_skills_value(
            profile,
            as_string=str(config.get("skills_value_format", "array")).lower() == "string",
        )
        if skills_value is not None:
            path = str(skills_path)
            submissions.append({"path": path, "value": skills_value})
            used_paths.add(path)


def build_education_history(profile: ProfileData) -> list[dict[str, Any]]:
    """Ashby EducationHistory values for configured application-form paths."""
    rows: list[dict[str, Any]] = []
    for entry in applicable_education(profile):
        row: dict[str, Any] = {"schoolName": entry.school.strip()}
        degree = entry.degree.strip()
        if degree:
            row["degree"] = degree
        major = entry.field_of_study.strip()
        if major:
            row["major"] = major
        if entry.start_year:
            row["startDate"] = f"{entry.start_year}-09-01"
        if entry.end_year:
            row["endDate"] = f"{entry.end_year}-05-15"
        rows.append(row)
    return rows


def build_work_history_text(profile: ProfileData) -> str | None:
    """Plain-text work history for Ashby String application-form fields."""
    entries = applicable_work_experience(profile)
    if not entries:
        return None
    return "\n".join(format_work_experience_entry(entry) for entry in entries)


def build_skills_value(profile: ProfileData, *, as_string: bool) -> list[str] | str | None:
    """Skills payload for Ashby MultiValueSelect or String fields."""
    skills = applicable_skills(profile)
    if not skills:
        return None
    if as_string:
        return ", ".join(skills)
    return skills
