"""Phenom People apply adapter.

Phenom careers sites (``POST /widgets``) often redirect apply to a downstream
ATS. Cisco/Splunk postings use Workday ``applyUrl`` values. This adapter:

1. Resolves job detail via ``ddoKey=jobDetail`` (or ``config.apply_url``).
2. Delegates to the matching applier when ``applyUrl`` is a known ATS.
3. Falls back to the partner Apply API (``POST /apply/v2/applications``) for
   Phenom-hosted applications.

Config / context:
  - ``config["careers_base_url"]``, ``country``, ``locale``, ``ref_num``.
  - ``config["apply_url"]`` / ``external_apply_url`` skips the widgets fetch.
  - ``config["applicant_source"]`` (default ``HeadStart``).
  - ``config["phenom_apply_api_base"]`` overrides the partner API origin.
  - Profile ``answers`` keys ``phenom_<field>`` map to ``customFieldData``.
  - Live partner submit requires credential ``session.access_token`` (OAuth).

Dry-run previews the delegated ATS payload or the partner application JSON.
Live Workday/Greenhouse/etc. submit uses that adapter's credential rules;
live Phenom-hosted submit needs a partner OAuth bearer token.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.phenom_common import (
    job_page_url,
    parse_session_html,
    resolve_careers_base_url,
    resolve_country,
    resolve_external_apply_url,
    resolve_job_id,
    resolve_locale,
    resolve_ref_num,
    search_results_url,
)
from app.appliers.adapters.phenom_detail import (
    PhenomJobDetail,
    detail_from_override,
    job_from_detail_response,
)
from app.appliers.adapters.phenom_hosted import apply_hosted
from app.appliers.adapters.phenom_route import PhenomApplyRoute, resolve_apply_route
from app.appliers.base import Applier, get_applier, register_applier
from app.appliers.types import ApplyContext, ApplyResult


@register_applier("phenom")
class PhenomApplier(Applier):
    """Apply via downstream ATS delegation or the Phenom partner Apply API."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        job_id = resolve_job_id(ctx.config, ctx.job_external_id, ctx.job_url)
        if not job_id:
            return ApplyResult(
                status="failed",
                error=(
                    "phenom applier needs a job id in job_external_id, "
                    "config.job_id, or a /job/<id> URL"
                ),
            )

        careers_base = resolve_careers_base_url(ctx.config, ctx.job_url)
        country = resolve_country(ctx.config, ctx.job_url)
        locale = resolve_locale(ctx.config, ctx.job_url)
        ref_num = resolve_ref_num(ctx.config, ctx.credentials)

        try:
            detail = self._resolve_detail(
                ctx,
                job_id=job_id,
                careers_base=careers_base,
                country=country,
                locale=locale,
                ref_num=ref_num,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc))

        route = resolve_apply_route(detail, careers_base_url=careers_base)
        if route.kind == "external_ats":
            return self._delegate(ctx, detail, route)
        if route.kind == "phenom_hosted":
            return apply_hosted(
                self.http,
                ctx,
                detail,
                careers_base=careers_base,
                locale=locale,
            )
        return ApplyResult(
            status="failed",
            error=route.reason or "phenom posting cannot be auto-applied",
            payload={
                "phenom_route": route.kind,
                "apply_url": detail.apply_url,
                "job_id": detail.job_id,
            },
        )

    def _resolve_detail(
        self,
        ctx: ApplyContext,
        *,
        job_id: str,
        careers_base: str | None,
        country: str,
        locale: str,
        ref_num: str,
    ) -> PhenomJobDetail:
        override = resolve_external_apply_url(ctx.config)
        if override is not None:
            return detail_from_override(
                job_id=job_id,
                title=ctx.job_title,
                apply_url=override,
                ref_num=ref_num,
            )
        if not careers_base:
            raise ValueError(
                "phenom applier needs config.careers_base_url or a careers job URL "
                "(or set config.apply_url to skip jobDetail fetch)"
            )

        csrf, discovered_ref = self._init_session(careers_base, country, locale)
        effective_ref = ref_num or discovered_ref
        data = self._fetch_job_detail(
            careers_base=careers_base,
            country=country,
            locale=locale,
            job_id=job_id,
            ref_num=effective_ref,
            csrf=csrf,
        )
        detail = job_from_detail_response(data, fallback_job_id=job_id)
        if detail is None:
            raise ValueError("phenom jobDetail response did not include a job object")
        return detail

    def _init_session(self, careers_base: str, country: str, locale: str) -> tuple[str | None, str]:
        html = self.http.get_text(search_results_url(careers_base, country, locale))
        return parse_session_html(html)

    def _fetch_job_detail(
        self,
        *,
        careers_base: str,
        country: str,
        locale: str,
        job_id: str,
        ref_num: str,
        csrf: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "lang": locale,
            "deviceType": "desktop",
            "country": country,
            "pageName": "job-details",
            "ddoKey": "jobDetail",
            "jobId": job_id,
            "jobSeqNo": job_id,
            "siteType": "external",
        }
        if ref_num:
            payload["refNum"] = ref_num
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": careers_base,
            "Referer": job_page_url(careers_base, country, locale, job_id),
        }
        if csrf:
            headers["x-csrf-token"] = csrf
        data = self.http.post_json(
            f"{careers_base.rstrip('/')}/widgets",
            json=payload,
            headers=headers,
        )
        if not isinstance(data, dict):
            raise ValueError("phenom jobDetail returned unexpected payload")
        return data

    def _delegate(
        self, ctx: ApplyContext, detail: PhenomJobDetail, route: PhenomApplyRoute
    ) -> ApplyResult:
        assert route.adapter_key is not None
        assert route.external_id is not None
        assert route.job_url is not None

        merged_config = {**ctx.config, **route.config}
        delegated = ApplyContext(
            job_external_id=route.external_id,
            job_title=ctx.job_title or detail.title,
            company=ctx.company,
            job_url=route.job_url,
            config=merged_config,
            profile=ctx.profile,
            resume_file=ctx.resume_file,
            credentials=ctx.credentials,
            cover_letter=ctx.cover_letter,
            dry_run=ctx.dry_run,
        )
        result = get_applier(route.adapter_key, http=self.http).apply(delegated)
        wrapper: dict[str, Any] = {
            "phenom_route": "external_ats",
            "delegated_adapter": route.adapter_key,
            "phenom_job_id": detail.job_id,
            "apply_url": detail.apply_url,
            "delegated_payload": result.payload,
        }
        if result.payload is not None:
            wrapper = {**result.payload, **wrapper}
        return ApplyResult(
            status=result.status,
            error=result.error,
            payload=wrapper,
            external_application_id=result.external_application_id,
        )
