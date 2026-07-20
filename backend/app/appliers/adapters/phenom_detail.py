"""Job-detail parsing for Phenom People apply."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PhenomJobDetail:
    """Normalized Phenom job fields needed to choose an apply route."""

    job_id: str
    title: str
    apply_url: str | None
    external_apply: bool
    ref_num: str
    raw: dict[str, Any]


def job_from_detail_response(data: object, *, fallback_job_id: str = "") -> PhenomJobDetail | None:
    """Parse a ``ddoKey=jobDetail`` widgets response into a job detail."""
    if not isinstance(data, dict):
        return None
    block = data.get("jobDetail")
    if not isinstance(block, dict):
        return None
    inner = block.get("data")
    job: dict[str, Any] | None = None
    if isinstance(inner, dict) and isinstance(inner.get("job"), dict):
        job = inner["job"]
    elif isinstance(block.get("job"), dict):
        job = block["job"]
    if job is None:
        return None
    return detail_from_job(job, fallback_job_id=fallback_job_id)


def detail_from_job(job: dict[str, Any], *, fallback_job_id: str = "") -> PhenomJobDetail | None:
    """Normalize one Phenom job object (search hit or jobDetail.job)."""
    job_id = str(
        job.get("jobSeqNo") or job.get("jobId") or job.get("reqId") or fallback_job_id or ""
    ).strip()
    if not job_id:
        return None
    title = str(job.get("title") or "").strip()
    apply_url = _apply_url_from_job(job)
    external_apply = bool(job.get("externalApply"))
    ref_num = str(job.get("refNum") or job.get("parentRefNum") or "").strip()
    return PhenomJobDetail(
        job_id=job_id,
        title=title,
        apply_url=apply_url,
        external_apply=external_apply,
        ref_num=ref_num,
        raw=job,
    )


def detail_from_override(
    *,
    job_id: str,
    title: str,
    apply_url: str | None,
    ref_num: str = "",
) -> PhenomJobDetail:
    """Build a detail when the operator supplies ``config.apply_url``."""
    return PhenomJobDetail(
        job_id=job_id,
        title=title,
        apply_url=apply_url,
        external_apply=bool(apply_url),
        ref_num=ref_num,
        raw={},
    )


def _apply_url_from_job(job: dict[str, Any]) -> str | None:
    for key in ("applyUrl", "apply_url", "externalApplyUrl", "external_apply_url"):
        value = job.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
