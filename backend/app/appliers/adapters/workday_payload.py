"""Workday CXS application payload builders."""

from __future__ import annotations

from typing import Any

from app.schemas.profile import ProfileData


def split_name(full_name: str) -> tuple[str, str]:
    """Split a display name into first and last components."""
    parts = full_name.strip().split(None, 1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


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


def build_supplemental_text(
    profile: ProfileData,
    *,
    company: str,
    job_title: str,
    cover_letter: str | None,
) -> str | None:
    """Cover letter (override or template) plus optional resume text."""
    parts: list[str] = []
    if cover_letter and cover_letter.strip():
        parts.append(cover_letter.strip())
    else:
        template = profile.cover_letter_template.strip()
        if template:
            parts.append(render_cover_letter(template, company=company, job_title=job_title))

    resume = profile.resume_text.strip()
    if resume:
        parts.append(f"Resume:\n{resume}")

    return "\n\n".join(parts) if parts else None


def build_application_payload(
    profile: ProfileData,
    *,
    job_posting_id: str,
    job_path: str,
    job_title: str,
    company: str,
    config: dict[str, Any],
    cover_letter: str | None = None,
) -> dict[str, Any]:
    """Map profile data to the Workday CXS apply payload shape."""
    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name or not last_name:
        raise ValueError("profile full_name must include first and last name")
    if not email:
        raise ValueError("profile email is required to apply")

    country_id = str(config.get("country_id") or "US")
    payload: dict[str, Any] = {
        "jobPostingId": job_posting_id,
        "jobPath": job_path,
        "applyMethod": str(config.get("apply_method") or "manual"),
        "candidate": {
            "legalName": {
                "firstName": first_name,
                "lastName": last_name,
                "country": {"id": country_id},
            },
            "emailAddress": email,
        },
    }

    phone = profile.phone.strip()
    if phone:
        payload["candidate"]["phoneNumber"] = phone

    location = profile.location.strip()
    if location:
        payload["candidate"]["location"] = location

    links: dict[str, str] = {}
    if profile.links.linkedin.strip():
        links["linkedIn"] = profile.links.linkedin.strip()
    if profile.links.github.strip():
        links["github"] = profile.links.github.strip()
    if profile.links.website.strip():
        links["website"] = profile.links.website.strip()
    if links:
        payload["candidate"]["links"] = links

    supplemental = build_supplemental_text(
        profile, company=company, job_title=job_title, cover_letter=cover_letter
    )
    if supplemental:
        payload["candidate"]["comments"] = supplemental

    for key, value in profile.answers.items():
        if value:
            payload.setdefault("answers", {})[key] = value

    return payload


def build_name_body(profile: ProfileData, config: dict[str, Any]) -> dict[str, Any]:
    """Body for POST jobapplication/{id}/name."""
    first_name, last_name = split_name(profile.full_name)
    country_id = str(config.get("country_id") or "US")
    return {
        "legalName": {
            "firstName": first_name,
            "lastName": last_name,
            "country": {"id": country_id},
        },
        "preferredCheck": False,
    }
