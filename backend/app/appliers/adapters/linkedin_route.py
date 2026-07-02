"""Resolve how a LinkedIn posting should be applied to."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.appliers.adapters.indeed_route import parse_ats_job_url
from app.appliers.adapters.linkedin_common import decode_linkedin_redirect
from app.appliers.adapters.linkedin_detail import LinkedInJobDetail
from app.appliers.base import has_applier


@dataclass(frozen=True, slots=True)
class LinkedInApplyRoute:
    """Resolved apply strategy for one LinkedIn posting."""

    kind: str  # external_ats | linkedin_hosted | unsupported
    adapter_key: str | None
    external_id: str | None
    job_url: str | None
    config: dict[str, Any]
    reason: str | None = None


def resolve_apply_route(detail: LinkedInJobDetail) -> LinkedInApplyRoute:
    """Pick external ATS delegation, LinkedIn-hosted Easy Apply, or unsupported."""
    if detail.expired:
        return LinkedInApplyRoute(
            kind="unsupported",
            adapter_key=None,
            external_id=None,
            job_url=None,
            config={},
            reason="linkedin posting is expired or no longer accepting applications",
        )

    if detail.external_apply_url:
        target = parse_ats_job_url(decode_linkedin_redirect(detail.external_apply_url))
        if target is not None and has_applier(target.adapter_key):
            return LinkedInApplyRoute(
                kind="external_ats",
                adapter_key=target.adapter_key,
                external_id=target.external_id,
                job_url=target.job_url,
                config=target.config,
            )
        if target is not None:
            return LinkedInApplyRoute(
                kind="unsupported",
                adapter_key=target.adapter_key,
                external_id=target.external_id,
                job_url=target.job_url,
                config=target.config,
                reason=(
                    f"linkedin listing redirects to {target.adapter_key}, "
                    "which has no apply adapter"
                ),
            )
        return LinkedInApplyRoute(
            kind="unsupported",
            adapter_key=None,
            external_id=None,
            job_url=detail.external_apply_url,
            config={},
            reason=(
                "linkedin listing uses an external apply URL that is not a supported ATS "
                f"({detail.external_apply_url})"
            ),
        )

    if detail.easy_apply:
        return LinkedInApplyRoute(
            kind="linkedin_hosted",
            adapter_key="linkedin",
            external_id=detail.job_id,
            job_url=None,
            config={},
        )

    if detail.offsite_apply:
        return LinkedInApplyRoute(
            kind="unsupported",
            adapter_key=None,
            external_id=None,
            job_url=None,
            config={},
            reason=(
                "linkedin offsite apply URL was not found; add LinkedIn session cookies "
                "via site credentials or set config.external_apply_url"
            ),
        )

    return LinkedInApplyRoute(
        kind="unsupported",
        adapter_key=None,
        external_id=None,
        job_url=None,
        config={},
        reason="linkedin posting has no Easy Apply button and no external ATS apply URL",
    )
