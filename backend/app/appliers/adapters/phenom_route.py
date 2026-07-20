"""Resolve how a Phenom People posting should be applied to."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.appliers.adapters.indeed_route import parse_ats_job_url
from app.appliers.adapters.phenom_detail import PhenomJobDetail
from app.appliers.base import has_applier


@dataclass(frozen=True, slots=True)
class PhenomApplyRoute:
    """Resolved apply strategy for one Phenom posting."""

    kind: str  # external_ats | phenom_hosted | unsupported
    adapter_key: str | None
    external_id: str | None
    job_url: str | None
    config: dict[str, Any]
    reason: str | None = None


def resolve_apply_route(
    detail: PhenomJobDetail, *, careers_base_url: str | None = None
) -> PhenomApplyRoute:
    """Pick downstream ATS delegation, Phenom partner Apply API, or unsupported."""
    if detail.apply_url:
        apply_url = _strip_apply_suffix(detail.apply_url)
        target = parse_ats_job_url(apply_url)
        if target is not None and has_applier(target.adapter_key):
            return PhenomApplyRoute(
                kind="external_ats",
                adapter_key=target.adapter_key,
                external_id=target.external_id,
                job_url=target.job_url,
                config=target.config,
            )
        if target is not None:
            return PhenomApplyRoute(
                kind="unsupported",
                adapter_key=target.adapter_key,
                external_id=target.external_id,
                job_url=target.job_url,
                config=target.config,
                reason=(
                    f"phenom listing redirects to {target.adapter_key}, "
                    "which has no apply adapter"
                ),
            )
        if _same_careers_host(detail.apply_url, careers_base_url):
            return PhenomApplyRoute(
                kind="phenom_hosted",
                adapter_key="phenom",
                external_id=detail.job_id,
                job_url=detail.apply_url,
                config={},
            )
        return PhenomApplyRoute(
            kind="unsupported",
            adapter_key=None,
            external_id=None,
            job_url=detail.apply_url,
            config={},
            reason=(
                "phenom listing uses an external apply URL that is not a supported ATS "
                f"({detail.apply_url})"
            ),
        )

    return PhenomApplyRoute(
        kind="phenom_hosted",
        adapter_key="phenom",
        external_id=detail.job_id,
        job_url=None,
        config={},
    )


def _strip_apply_suffix(url: str) -> str:
    """Drop trailing ``/apply`` so Workday URL parsers see the job slug."""
    cleaned = url.strip()
    if cleaned.lower().endswith("/apply"):
        return cleaned[: -len("/apply")]
    return cleaned


def _same_careers_host(apply_url: str, careers_base_url: str | None) -> bool:
    if not careers_base_url:
        return False
    apply_host = urlparse(apply_url).netloc.lower()
    base_host = urlparse(careers_base_url).netloc.lower()
    return bool(apply_host and base_host and apply_host == base_host)
