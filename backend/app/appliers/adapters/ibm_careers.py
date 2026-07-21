"""IBM Careers apply adapter (Avature-hosted portal).

IBM Careers listings (``careers.ibm.com/careers/JobDetail?jobId=…``, including
post-acquisition HashiCorp roles) scrape via the public Falcon search API, but
applications run on an Avature portal behind AWS WAF with a multi-step
login/register wizard. There is no unauthenticated public apply POST.

This adapter therefore:

1. Dry-runs a preview of the candidate CSV + portal apply URLs.
2. Live-submits via Avature **External Import Services** when the operator
   supplies a provisioned ``ImportService`` endpoint (same class of gate as
   iCIMS Partner API credentials).

Config / context:
  - ``config["job_id"]`` / ``jobId``: optional numeric job id override.
  - ``config["careers_base_url"]``: portal origin (default ``careers.ibm.com``).
  - ``config["avature_import_url"]`` / ``import_url``: Import Service endpoint
    (required for live submit; also accepted on credential ``session``).
  - ``config["import_csv_columns"]``: ordered CSV columns (tenant layout).
  - ``config["import_csv_header"]``: include a header row (default false).
  - Credential ``session.api_key`` / ``avature_api_key``: optional
    ``X-Avature-Key`` when the Import Service requires it.

Dry-run never hits careers.ibm.com (WAF). Live submit POSTs multipart CSV to
the Import Service URL only.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.ibm_careers_common import (
    application_methods_url,
    extract_error_message,
    extract_import_code,
    job_detail_url,
    resolve_api_key,
    resolve_careers_base_url,
    resolve_import_url,
    resolve_job_id,
)
from app.appliers.adapters.ibm_careers_payload import (
    build_candidate_row,
    build_csv_bytes,
    build_dry_run_payload,
    csv_columns,
)
from app.appliers.base import Applier, register_applier
from app.appliers.text import render_cover_letter
from app.appliers.types import ApplyContext, ApplyResult

_LIVE_BLOCKER = (
    "ibm_careers live apply requires config.avature_import_url (or "
    "session.avature_import_url) pointing at an Avature External Import "
    "Service endpoint — careers.ibm.com apply is Avature-hosted behind AWS "
    "WAF with a multi-step login/register wizard and no public candidate "
    "apply API"
)


@register_applier("ibm_careers")
class IbmCareersApplier(Applier):
    """Apply via Avature External Import Services for IBM Careers jobs."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        job_id = resolve_job_id(ctx.config, ctx.job_external_id, ctx.job_url)
        if not job_id:
            return ApplyResult(
                status="failed",
                error=(
                    "ibm_careers applier needs a numeric job id in "
                    "job_external_id, config.job_id, or a JobDetail URL"
                ),
            )

        careers_base = resolve_careers_base_url(ctx.config, ctx.job_url)
        detail_url = job_detail_url(careers_base, job_id)
        methods_url = application_methods_url(careers_base, job_id)
        import_url = resolve_import_url(ctx.config, ctx.credentials)

        cover_letter = ctx.cover_letter
        if cover_letter is None and ctx.profile.cover_letter_template.strip():
            cover_letter = render_cover_letter(
                ctx.profile.cover_letter_template,
                company=ctx.company,
                job_title=ctx.job_title,
            )

        try:
            row = build_candidate_row(
                ctx.profile,
                job_id=job_id,
                cover_letter=cover_letter,
                resume_file=ctx.resume_file,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))

        columns = csv_columns(ctx.config)
        preview = build_dry_run_payload(
            row=row,
            columns=columns,
            job_id=job_id,
            careers_base_url=careers_base,
            job_detail_url=detail_url,
            application_methods_url=methods_url,
            import_url=import_url,
            resume_file=ctx.resume_file,
        )

        if ctx.dry_run:
            return ApplyResult(status="dry_run", payload=preview)

        if not import_url:
            return ApplyResult(status="failed", error=_LIVE_BLOCKER, payload=preview)

        include_header = bool(ctx.config.get("import_csv_header") or ctx.config.get("csv_header"))
        csv_body = build_csv_bytes(row, columns=columns, include_header=include_header)
        headers: dict[str, str] = {}
        api_key = resolve_api_key(ctx.credentials, ctx.config)
        if api_key:
            headers["X-Avature-Key"] = api_key

        files: dict[str, Any] = {
            "upload": ("candidates.csv", csv_body, "text/csv"),
        }
        data: dict[str, Any] = {}
        return_url = str(ctx.config.get("import_return_url") or "").strip()
        if return_url:
            data["returnUrl"] = return_url

        try:
            response = self.http.post_multipart(import_url, data=data, files=files, headers=headers)
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc), payload=preview)

        if not _import_accepted(response):
            return ApplyResult(
                status="failed",
                error=extract_error_message(response),
                payload={**preview, "import_response": _safe_response(response)},
            )

        return ApplyResult(
            status="submitted",
            external_application_id=extract_import_code(response),
            payload={**preview, "import_response": _safe_response(response)},
        )


def _import_accepted(response: object) -> bool:
    if isinstance(response, dict):
        result = str(response.get("result") or "").strip().lower()
        if result == "accepted":
            return True
        if result == "error":
            return False
        # Some tenants omit result and only set importCode on success.
        return extract_import_code(response) is not None and not response.get("error")
    return False


def _safe_response(response: object) -> object:
    if isinstance(response, dict):
        return {key: value for key, value in response.items() if key != "upload"}
    if isinstance(response, str):
        return response[:2000]
    return response
