"""Phenom People URL detection helpers."""

from __future__ import annotations

from typing import Any

from app.scrapers.url_detect_types import SourceDetection

# Canonical Phenom hosts (not vanity redirect domains — CSRF is host-scoped).
_KNOWN_HOSTS: dict[str, dict[str, str]] = {
    "careers.cisco.com": {
        "company": "Cisco",
        "country": "global",
        "locale": "en_global",
        "ref_num": "CISCISGLOBAL",
    },
}


def detect_phenom(parsed: Any, host: str, page_title: str | None) -> SourceDetection | None:
    """Return adapter defaults when the URL matches a known Phenom careers site."""
    known = _KNOWN_HOSTS.get(host)
    path_parts = [part for part in parsed.path.split("/") if part]
    if known is None:
        # Explicit /widgets path on an otherwise unknown host still maps to phenom
        # when the operator pasted the widget endpoint.
        if not path_parts or path_parts[0] != "widgets":
            return None
        company = _suggested_name(page_title, _humanize_slug(host.split(".")[0]))
        base_url = f"{parsed.scheme}://{host}"
        return SourceDetection(
            adapter_key="phenom",
            suggested_name=company,
            base_url=base_url,
            default_config={"careers_base_url": base_url, "company": company},
            query_url=base_url,
        )

    company = known["company"]
    config: dict[str, str] = {
        "careers_base_url": f"https://{host}",
        "company": company,
        "country": known["country"],
        "locale": known["locale"],
        "ref_num": known["ref_num"],
    }
    # Cisco hosts Splunk roles under /.../splunk — seed keyword filter for that brand.
    if host == "careers.cisco.com" and any(part.lower() == "splunk" for part in path_parts):
        company = "Splunk"
        config["company"] = "Splunk"
        config["keywords"] = "Splunk"

    suggested_name = _suggested_name(page_title, company)
    base_url = f"https://{host}"
    return SourceDetection(
        adapter_key="phenom",
        suggested_name=suggested_name,
        base_url=base_url,
        default_config=config,
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
