"""SuccessFactors Career Site Builder URL detection helpers."""

from __future__ import annotations

from typing import Any

from app.scrapers.url_detect_types import SourceDetection

_CLOUD_HOST_SUFFIX = ".jobs.hr.cloud.sap"
_API_PATH = "/services/recruiting/v1/jobs"
_KNOWN_HOSTS: dict[str, dict[str, str]] = {
    "wlgore.jobs.hr.cloud.sap": {
        "company": "W. L. Gore & Associates",
        "portal_id": "wlgore",
    },
}


def detect_successfactors(
    parsed: Any, host: str, page_title: str | None
) -> SourceDetection | None:
    """Return adapter defaults for ``*.jobs.hr.cloud.sap`` or recruiting jobs URLs."""
    known = _KNOWN_HOSTS.get(host)
    is_cloud = host.endswith(_CLOUD_HOST_SUFFIX) and host != "jobs.hr.cloud.sap"
    is_api = _API_PATH in (parsed.path or "")
    if not known and not is_cloud and not is_api:
        return None

    base_url = f"https://{host}"
    if known:
        company = known["company"]
        config: dict[str, str] = {
            "careers_base_url": base_url,
            "company": company,
            "portal_id": known["portal_id"],
        }
    else:
        company = _company_from_host(host)
        config = {"careers_base_url": base_url, "company": company}

    return SourceDetection(
        adapter_key="successfactors",
        suggested_name=_suggested_name(page_title, company),
        base_url=base_url,
        default_config=config,
        query_url=base_url,
    )


def _company_from_host(host: str) -> str:
    if host.endswith(_CLOUD_HOST_SUFFIX):
        slug = host[: -len(_CLOUD_HOST_SUFFIX)]
        if "." in slug:
            slug = slug.split(".")[0]
        return _humanize_slug(slug) if slug else host
    return host


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
