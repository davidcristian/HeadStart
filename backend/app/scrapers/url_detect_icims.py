"""iCIMS / Jibe Attract URL detection helpers."""

from __future__ import annotations

from typing import Any

from app.scrapers.url_detect_types import SourceDetection

# Branded Jibe Attract hosts verified to expose GET /api/jobs JSON.
_KNOWN_VANITY_HOSTS: dict[str, str] = {
    "careers.rivian.com": "Rivian",
}


def detect_icims(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    """Return adapter defaults when the URL matches an iCIMS/Jibe careers surface."""
    company = ""
    base_url = ""

    if host.endswith(".jibeapply.com") and host != "jibeapply.com":
        slug = host[: -len(".jibeapply.com")]
        if not slug or "." in slug:
            return None
        company = _humanize_slug(slug)
        base_url = f"https://{host}"
    elif host in _KNOWN_VANITY_HOSTS:
        company = _KNOWN_VANITY_HOSTS[host]
        base_url = f"https://{host}"
    else:
        path_parts = [part for part in parsed.path.split("/") if part]
        if path_parts[:2] != ["api", "jobs"]:
            return None
        company = _suggested_name(page_title, _humanize_slug(host.split(".")[0]))
        base_url = f"{parsed.scheme}://{host}"

    suggested_name = _suggested_name(page_title, company or _humanize_slug(host.split(".")[0]))
    return SourceDetection(
        adapter_key="icims",
        suggested_name=suggested_name,
        base_url=base_url,
        default_config={
            "careers_base_url": base_url,
            "company": company or suggested_name,
        },
        query_url=base_url,
    )


def _humanize_slug(slug: str) -> str:
    cleaned = slug.replace("-", " ").replace("_", " ").strip()
    return cleaned.title() if cleaned else slug


def _suggested_name(page_title: str | None, fallback: str) -> str:
    if not page_title:
        return fallback
    cleaned = page_title.strip()
    for suffix in (" Careers", " Jobs", " Job Board", " | Careers", " - Careers"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    return cleaned or fallback
