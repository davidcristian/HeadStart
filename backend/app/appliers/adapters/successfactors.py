"""SAP SuccessFactors apply adapter (OData Recruiting).

Career Site Builder boards (``*.jobs.hr.cloud.sap``) expose a public jobs search
API but route applications through a login-gated Talent Community wizard
(``/talentcommunity/apply/<id>/``). There is no unauthenticated public apply
POST comparable to Greenhouse.

This adapter therefore:

1. Dry-runs a preview of the OData ``Candidate`` + ``JobApplication`` payloads
   and the portal apply URL.
2. Live-submits via SuccessFactors Recruiting OData when the operator supplies
   an API host, company id, and API-user Basic Auth (same class of gate as
   iCIMS Partner API credentials).

Config / context:
  - ``config["careers_base_url"]``: CSB origin (optional; from ``job_url``).
  - ``config["locale"]``: apply URL locale (default ``en_US``).
  - ``config["job_req_id"]`` / ``job_id``: optional requisition id override.
  - ``config["odata_base_url"]`` / ``api_base_url``: API host (required live).
  - ``config["company_id"]`` / ``sf_company_id``: SF company id (required live).
  - ``config["country"]``: Candidate country (default ``United States``).
  - Profile ``answers`` keys ``sf_<field>`` map onto JobApplication fields.
  - Credential ``session.username`` + ``session.password`` (aliases:
    ``basic_auth_*``, ``api_*``, ``sf_*``, ``odata_*``) for OData Basic Auth.

Dry-run never calls the OData host. Live submit POSTs Candidate (optional
Attachment) then JobApplication.
"""

from __future__ import annotations

from app.appliers.adapters.successfactors_common import (
    basic_auth_header,
    resolve_basic_auth,
    resolve_careers_base_url,
    resolve_company_id,
    resolve_country,
    resolve_job_id,
    resolve_locale,
    resolve_odata_base_url,
    talentcommunity_apply_url,
)
from app.appliers.adapters.successfactors_payload import (
    build_application_payload,
    build_attachment_payload,
    build_candidate_payload,
    build_dry_run_payload,
)
from app.appliers.adapters.successfactors_submit import live_submit
from app.appliers.base import Applier, register_applier
from app.appliers.text import render_cover_letter
from app.appliers.types import ApplyContext, ApplyResult

_LIVE_BLOCKER = (
    "successfactors live apply requires config.odata_base_url (or "
    "session.odata_base_url) and company_id plus API user Basic Auth. "
    "Career Site Builder /talentcommunity/apply/ is login-gated with no "
    "public candidate apply API"
)


@register_applier("successfactors")
class SuccessFactorsApplier(Applier):
    """Apply via SuccessFactors Recruiting OData (Candidate + JobApplication)."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        job_id = resolve_job_id(ctx.config, ctx.job_external_id, ctx.job_url)
        if not job_id:
            return ApplyResult(
                status="failed",
                error=(
                    "successfactors applier needs a numeric job id in "
                    "job_external_id, config.job_req_id, or a /job/…/<id>-locale URL"
                ),
            )

        careers_base = resolve_careers_base_url(ctx.config, ctx.job_url)
        locale = resolve_locale(ctx.config)
        apply_url = (
            talentcommunity_apply_url(careers_base, job_id, locale) if careers_base else None
        )
        odata_base = resolve_odata_base_url(ctx.config, ctx.credentials)
        company_id = resolve_company_id(ctx.config, ctx.credentials)
        country = resolve_country(ctx.config, ctx.profile.answers)

        cover_letter = ctx.cover_letter
        if cover_letter is None and ctx.profile.cover_letter_template.strip():
            cover_letter = render_cover_letter(
                ctx.profile.cover_letter_template,
                company=ctx.company,
                job_title=ctx.job_title,
            )

        agree = ctx.config.get("agree_to_privacy_statement")
        if agree is None:
            agree = True

        try:
            candidate = build_candidate_payload(
                ctx.profile,
                country=country,
                agree_to_privacy=bool(agree),
            )
            application = build_application_payload(
                ctx.profile,
                job_req_id=job_id,
                candidate_id=None,
                cover_letter=cover_letter,
                config=ctx.config,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))

        attachment_preview = None
        if ctx.resume_file is not None:
            attachment_preview = build_attachment_payload(ctx.resume_file)

        preview = build_dry_run_payload(
            candidate=candidate,
            application=application,
            job_id=job_id,
            careers_base_url=careers_base,
            apply_url=apply_url,
            odata_base_url=odata_base,
            company_id=company_id,
            locale=locale,
            resume_file=ctx.resume_file,
            attachment=attachment_preview,
        )

        if ctx.dry_run:
            return ApplyResult(status="dry_run", payload=preview)

        if not odata_base or not company_id:
            return ApplyResult(status="failed", error=_LIVE_BLOCKER, payload=preview)

        auth = resolve_basic_auth(ctx.credentials, ctx.config, company_id=company_id)
        if auth is None:
            return ApplyResult(
                status="failed",
                error=(
                    "successfactors live apply requires OData Basic Auth in "
                    "credential session.username + session.password "
                    "(aliases: basic_auth_*, api_*, sf_*, odata_*)"
                ),
                payload=preview,
            )

        headers = {
            "Authorization": basic_auth_header(*auth),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        return live_submit(
            self.http,
            ctx,
            headers=headers,
            odata_base=odata_base,
            company_id=company_id,
            job_id=job_id,
            careers_base=careers_base,
            apply_url=apply_url,
            locale=locale,
            candidate=candidate,
            cover_letter=cover_letter,
            attachment_preview=attachment_preview,
            preview=preview,
        )


__all__ = ["SuccessFactorsApplier"]
