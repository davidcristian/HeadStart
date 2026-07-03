"""Shared text helpers for apply adapters (cover-letter rendering, name splitting)."""

from __future__ import annotations


def render_cover_letter(template: str, *, company: str, job_title: str) -> str:
    """Substitute simple placeholders in a cover-letter template."""
    replacements = {
        "{company}": company,
        "{job_title}": job_title,
        "{title}": job_title,
    }
    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result


def split_name(full_name: str) -> tuple[str, str]:
    """Split a display name into first and last components (last may be empty).

    SmartRecruiters needs a non-empty last name and keeps its own variant in
    `smartrecruiters_common.split_name`; every other adapter shares this one.
    """
    parts = full_name.strip().split(None, 1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]
