"""Heuristic cover-letter generator used as the offline default.

Builds a cover letter from the user's template (with placeholder substitution)
or a simple structured draft from profile fields. No API key or network required.
"""

from __future__ import annotations

from app.cover_letters.base import CoverLetterGenerator, register_cover_letter_generator
from app.cover_letters.template import render_cover_letter_template
from app.cover_letters.types import CoverLetterContext
from app.schemas.profile import ProfileData


@register_cover_letter_generator("heuristic")
class HeuristicCoverLetterGenerator(CoverLetterGenerator):
    """Draft a cover letter from profile data without external calls."""

    def __init__(self, *, settings: object | None = None) -> None:
        pass

    def generate(self, ctx: CoverLetterContext) -> str:
        return _build_letter(ctx)


def _build_letter(ctx: CoverLetterContext) -> str:
    profile = ctx.profile
    company = ctx.company.strip() or "the hiring team"
    job_title = ctx.job_title.strip() or "this role"
    template = profile.cover_letter_template.strip()
    paragraphs: list[str] = []

    if template:
        paragraphs.append(
            render_cover_letter_template(template, company=company, job_title=job_title)
        )
    else:
        greeting = f"Dear {company} hiring team,"
        paragraphs.append(
            f"{greeting}\n\n" f"I am writing to express my interest in the {job_title} position."
        )

    experience_line = _recent_experience_line(profile)
    if experience_line:
        paragraphs.append(experience_line)

    skills_line = _skills_line(profile)
    if skills_line:
        paragraphs.append(skills_line)

    if ctx.job_summary.strip():
        paragraphs.append(
            f"This opportunity stood out to me because {ctx.job_summary.strip().rstrip('.')}."
        )

    closing_name = profile.full_name.strip() or "Sincerely"
    paragraphs.append(f"Thank you for your consideration.\n\n{closing_name}")
    return "\n\n".join(part for part in paragraphs if part.strip())


def _recent_experience_line(profile: ProfileData) -> str:
    for entry in profile.work_experience:
        title = entry.job_title.strip()
        company = entry.company.strip()
        if title and company:
            return (
                f"In my recent role as {title} at {company}, "
                f"I built experience relevant to this opportunity."
            )
        if title:
            return f"My background as {title} aligns well with what you are looking for."
    if profile.resume_text.strip():
        excerpt = profile.resume_text.strip().split("\n", 1)[0]
        if len(excerpt) > 200:
            excerpt = excerpt[:199].rstrip() + "…"
        return f"My background includes: {excerpt}"
    return ""


def _skills_line(profile: ProfileData) -> str:
    skills = [skill.strip() for skill in profile.skills if skill.strip()]
    if not skills:
        return ""
    shown = skills[:6]
    tail = ", ".join(shown[:-1]) + f", and {shown[-1]}" if len(shown) > 1 else shown[0]
    return f"Key strengths I would bring include {tail}."
