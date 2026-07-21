"""Payload builders for the IBM Careers (Avature) apply adapter."""

from __future__ import annotations

import base64
import csv
import io
from typing import Any

from app.appliers.resume import resume_meta_for_payload
from app.appliers.text import split_name
from app.schemas.profile import ProfileData, ResumeFile

# Default CSV column order for Avature External Import Services.
# Operators must map these columns to Person / Job fields in the Avature
# Import Data UI because the layout is tenant-specific.
DEFAULT_CSV_COLUMNS: tuple[str, ...] = (
    "first_name",
    "last_name",
    "email",
    "phone",
    "job_id",
    "location",
    "linkedin",
    "website",
    "cover_letter",
    "resume_filename",
    "resume_content_type",
    "resume_base64",
)


def build_candidate_row(
    profile: ProfileData,
    *,
    job_id: str,
    cover_letter: str | None = None,
    resume_file: ResumeFile | None = None,
) -> dict[str, str]:
    """Map an application profile to Import Service CSV column values."""
    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name or not last_name:
        raise ValueError("profile full_name must include first and last name")
    if not email:
        raise ValueError("profile email is required to apply")

    row: dict[str, str] = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": profile.phone.strip(),
        "job_id": job_id,
        "location": profile.location.strip(),
        "linkedin": (profile.links.linkedin or "").strip(),
        "website": (profile.links.website or "").strip(),
        "cover_letter": (cover_letter or "").strip(),
        "resume_filename": "",
        "resume_content_type": "",
        "resume_base64": "",
    }
    if resume_file is not None:
        row["resume_filename"] = resume_file.filename
        row["resume_content_type"] = resume_file.content_type
        row["resume_base64"] = base64.b64encode(resume_file.data).decode("ascii")
    return row


def csv_columns(config: dict[str, Any]) -> list[str]:
    """Ordered CSV columns from config or the HeadStart default layout."""
    raw = config.get("import_csv_columns") or config.get("avature_csv_columns")
    if isinstance(raw, str) and raw.strip():
        cols = [part.strip() for part in raw.split(",") if part.strip()]
        if cols:
            return cols
    if isinstance(raw, list):
        cols = [str(part).strip() for part in raw if str(part).strip()]
        if cols:
            return cols
    return list(DEFAULT_CSV_COLUMNS)


def build_csv_bytes(row: dict[str, str], *, columns: list[str], include_header: bool) -> bytes:
    """Serialize one candidate row as CSV for the Import Service ``upload`` field."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    if include_header:
        writer.writerow(columns)
    writer.writerow([row.get(col, "") for col in columns])
    return buffer.getvalue().encode("utf-8")


def build_dry_run_payload(
    *,
    row: dict[str, str],
    columns: list[str],
    job_id: str,
    careers_base_url: str,
    job_detail_url: str,
    application_methods_url: str,
    import_url: str | None,
    resume_file: ResumeFile | None = None,
) -> dict[str, Any]:
    """Preview envelope for dry-run (no network to Avature / WAF)."""
    # Never echo Base64 resume bytes into application_log previews.
    preview_row = {key: value for key, value in row.items() if key != "resume_base64"}
    if row.get("resume_base64"):
        preview_row["resume_base64"] = "<omitted>"
    payload: dict[str, Any] = {
        "ibm_careers_route": "avature_import" if import_url else "portal_blocked",
        "job_id": job_id,
        "careers_base_url": careers_base_url,
        "job_detail_url": job_detail_url,
        "application_methods_url": application_methods_url,
        "import_url": import_url,
        "import_csv_columns": columns,
        "candidate": preview_row,
        "blocker": (
            None
            if import_url
            else (
                "careers.ibm.com is Avature-hosted behind AWS WAF with a multi-step "
                "login/register apply wizard and no public candidate apply API. "
                "Dry-run previews the payload; live submit needs an Avature External "
                "Import Service URL (config.avature_import_url) provisioned for your "
                "tenant, or apply manually via application_methods_url."
            )
        ),
    }
    meta = resume_meta_for_payload(resume_file)
    if meta is not None:
        payload["resume"] = meta
    return payload
