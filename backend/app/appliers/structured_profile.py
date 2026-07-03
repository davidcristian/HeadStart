"""Shared helpers for mapping structured application profile rows to apply payloads."""

from __future__ import annotations

from app.schemas.profile import EducationEntry, ProfileData, WorkExperienceEntry


def applicable_work_experience(profile: ProfileData) -> list[WorkExperienceEntry]:
    """Profile rows with the minimum fields apply adapters need for work history."""
    return [
        entry
        for entry in profile.work_experience
        if (
            entry.job_title.strip()
            and entry.company.strip()
            and entry.start_year
            and entry.start_month
        )
    ]


def applicable_education(profile: ProfileData) -> list[EducationEntry]:
    """Profile rows with the minimum fields apply adapters need for education."""
    return [entry for entry in profile.education if entry.school.strip()]


def applicable_skills(profile: ProfileData) -> list[str]:
    """Non-empty skill labels from the application profile."""
    return [skill.strip() for skill in profile.skills if skill.strip()]


def format_work_experience_entry(entry: WorkExperienceEntry) -> str:
    """One human-readable work-experience line for supplemental text fields."""
    location = f" ({entry.location.strip()})" if entry.location.strip() else ""
    period = _format_period(entry)
    line = f"- {entry.job_title.strip()} at {entry.company.strip()}{location} ({period})"
    description = entry.description.strip()
    if description:
        line += f"\n  {description}"
    return line


def format_education_entry(entry: EducationEntry) -> str:
    """One human-readable education line for supplemental text fields."""
    degree_parts = [part for part in (entry.degree.strip(), entry.field_of_study.strip()) if part]
    school = entry.school.strip()
    header = f"- {', '.join(degree_parts)}, {school}" if degree_parts else f"- {school}"
    year_parts = [str(year) for year in (entry.start_year, entry.end_year) if year]
    if year_parts:
        header += f" ({' - '.join(year_parts)})"
    gpa = entry.gpa.strip()
    if gpa:
        header += f"; GPA {gpa}"
    return header


def build_profile_supplement(profile: ProfileData) -> str | None:
    """Formatted work history, education, and skills for free-text apply fields."""
    sections: list[str] = []
    work = applicable_work_experience(profile)
    if work:
        lines = "\n".join(format_work_experience_entry(entry) for entry in work)
        sections.append(f"Work experience:\n{lines}")

    education = applicable_education(profile)
    if education:
        lines = "\n".join(format_education_entry(entry) for entry in education)
        sections.append(f"Education:\n{lines}")

    skills = applicable_skills(profile)
    if skills:
        sections.append(f"Skills: {', '.join(skills)}")

    return "\n\n".join(sections) if sections else None


def _format_period(entry: WorkExperienceEntry) -> str:
    start = _format_month_year(entry.start_month, entry.start_year)
    if entry.is_current:
        return f"{start} - Present"
    end = _format_month_year(entry.end_month, entry.end_year)
    return f"{start} - {end}" if end else start


def _format_month_year(month: int | None, year: int | None) -> str:
    if year is None:
        return ""
    if month:
        return f"{month:02d}/{year}"
    return str(year)
