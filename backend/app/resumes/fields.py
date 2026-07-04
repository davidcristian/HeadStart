"""Format profile fields into resume placeholder text."""

from __future__ import annotations

from app.resumes.template import escape_latex
from app.resumes.types import CuratedResumeFields, ResumeCurationContext
from app.schemas.profile import EducationEntry, ProfileData, WorkExperienceEntry


def heuristic_fields(ctx: ResumeCurationContext) -> CuratedResumeFields:
    """Build resume placeholders from profile data without external calls."""
    profile = ctx.profile
    company = ctx.company.strip() or "the hiring team"
    job_title = ctx.job_title.strip() or "this role"
    return CuratedResumeFields(
        full_name=profile.full_name.strip(),
        email=profile.email.strip(),
        phone=profile.phone.strip(),
        location=profile.location.strip(),
        linkedin=profile.links.linkedin.strip(),
        github=profile.links.github.strip(),
        website=profile.links.website.strip(),
        job_title=job_title,
        company=company,
        summary=_summary(
            profile,
            job_title=job_title,
            company=company,
            job_summary=ctx.job_summary,
        ),
        experience=_experience(profile),
        education=_education(profile),
        skills=_skills(profile),
    )


def _summary(
    profile: ProfileData,
    *,
    job_title: str,
    company: str,
    job_summary: str,
) -> str:
    if profile.resume_text.strip():
        excerpt = profile.resume_text.strip().replace("\n", " ")
        if len(excerpt) > 500:
            excerpt = excerpt[:499].rstrip() + "…"
        lead = f"Experienced candidate targeting the {job_title} role at {company}."
        return f"{lead} {excerpt}"
    return f"Experienced professional interested in the {job_title} position at {company}." + (
        f" {job_summary.strip()}" if job_summary.strip() else ""
    )


def _experience(profile: ProfileData) -> str:
    items: list[str] = []
    for entry in profile.work_experience:
        block = _experience_item(entry)
        if block:
            items.append(block)
    if items:
        return "\n".join(items)
    if profile.resume_text.strip():
        return r"\item " + escape_latex(profile.resume_text.strip().split("\n", 1)[0][:300])
    return r"\item Relevant professional experience available upon request."


def _experience_item(entry: WorkExperienceEntry) -> str:
    title = entry.job_title.strip()
    company = entry.company.strip()
    if not title and not company:
        return ""
    if title and not company:
        header = title
    elif company and not title:
        header = company
    else:
        header = f"{title}, {company}"
    period = _period(entry)
    line = rf"\item \textbf{{{escape_latex(header)}}}"
    if period:
        line += f" ({period})"
    description = " ".join(
        part.strip().lstrip("-•*") for part in entry.description.splitlines() if part.strip()
    )
    if description:
        line += f" — {escape_latex(description[:500])}"
    return line


def _period(entry: WorkExperienceEntry) -> str:
    start = _month_year(entry.start_month, entry.start_year)
    if entry.is_current:
        return f"{start}–Present" if start else "Present"
    end = _month_year(entry.end_month, entry.end_year)
    if start and end:
        return f"{start}–{end}"
    return start or end


def _month_year(month: int | None, year: int | None) -> str:
    if year is None:
        return ""
    if month is None:
        return str(year)
    names = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    month_label = names[month] if 1 <= month <= 12 else str(month)
    return f"{month_label} {year}"


def _education(profile: ProfileData) -> str:
    lines: list[str] = []
    for entry in profile.education:
        line = _education_line(entry)
        if line:
            lines.append(line)
    return "\n\n".join(lines) if lines else "Education details available upon request."


def _education_line(entry: EducationEntry) -> str:
    school = entry.school.strip()
    if not school:
        return ""
    detail = ", ".join(
        part for part in (entry.degree.strip(), entry.field_of_study.strip()) if part
    )
    years = ""
    if entry.start_year and entry.end_year:
        years = f" ({entry.start_year}–{entry.end_year})"
    elif entry.end_year:
        years = f" ({entry.end_year})"
    suffix = f" — {detail}{years}" if detail or years else years
    return f"{school}{suffix}"


def _skills(profile: ProfileData) -> str:
    skills = [skill.strip() for skill in profile.skills if skill.strip()]
    if skills:
        return ", ".join(skills[:20])
    return ""
