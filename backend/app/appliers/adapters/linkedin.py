"""LinkedIn apply adapter.

LinkedIn listings either expose Easy Apply on LinkedIn itself or redirect to an
employer ATS. This adapter fetches the public guest job-posting page, optionally
enriches offsite listings via authenticated Voyager GraphQL, delegates to a
downstream applier when the employer apply URL is recognized, and previews or
submits LinkedIn-hosted Easy Apply jobs with logged-in session cookies.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.linkedin_common import (
    decode_linkedin_redirect,
    has_linkedin_session_cookies,
    resolve_job_posting_url,
    voyager_request_cookies,
    voyager_request_headers,
)
from app.appliers.adapters.linkedin_detail import (
    LinkedInJobDetail,
    merge_external_apply_url,
    parse_job_posting_page,
)
from app.appliers.adapters.linkedin_easy_apply import (
    SUBMIT_URL,
    build_easy_apply_payload,
    build_submit_body,
    extract_form_root,
)
from app.appliers.adapters.linkedin_route import LinkedInApplyRoute, resolve_apply_route
from app.appliers.adapters.linkedin_voyager import fetch_application_form, fetch_company_apply_url
from app.appliers.base import Applier, get_applier, register_applier
from app.appliers.types import ApplyContext, ApplyResult


@register_applier("linkedin")
class LinkedInApplier(Applier):
    """Apply to LinkedIn postings via downstream ATS delegation or Easy Apply."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        try:
            detail = self._resolve_detail(ctx)
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))

        route = resolve_apply_route(detail)
        if route.kind == "external_ats":
            return self._delegate(ctx, detail, route)
        if route.kind == "linkedin_hosted":
            return self._apply_hosted(ctx, detail)
        return ApplyResult(
            status="failed",
            error=route.reason or "linkedin posting cannot be auto-applied",
            payload={
                "route": route.kind,
                "external_apply_url": detail.external_apply_url,
                "easy_apply": detail.easy_apply,
                "offsite_apply": detail.offsite_apply,
            },
        )

    def _delegate(
        self,
        ctx: ApplyContext,
        detail: LinkedInJobDetail,
        route: LinkedInApplyRoute,
    ) -> ApplyResult:
        assert route.adapter_key is not None
        assert route.external_id is not None
        assert route.job_url is not None

        merged_config = {**ctx.config, **route.config}
        delegated = ApplyContext(
            job_external_id=route.external_id,
            job_title=ctx.job_title,
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
        wrapper = {
            "linkedin_route": "external_ats",
            "delegated_adapter": route.adapter_key,
            "linkedin_job_id": detail.job_id,
            "external_apply_url": detail.external_apply_url,
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

    def _apply_hosted(self, ctx: ApplyContext, detail: LinkedInJobDetail) -> ApplyResult:
        form_payload = None
        if has_linkedin_session_cookies(ctx.credentials):
            form_payload = fetch_application_form(self.http, detail.job_id, ctx.credentials)
        form_root = extract_form_root(form_payload) if form_payload else None
        try:
            payload = build_easy_apply_payload(
                detail,
                ctx.profile,
                company=ctx.company,
                job_title=ctx.job_title,
                cover_letter=ctx.cover_letter,
                resume_file=ctx.resume_file,
                form_payload=form_root,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))

        if ctx.dry_run:
            return ApplyResult(status="dry_run", payload=payload)

        if not has_linkedin_session_cookies(ctx.credentials):
            return ApplyResult(
                status="failed",
                error=(
                    "linkedin live Easy Apply requires logged-in session cookies "
                    "(li_at and JSESSIONID) in site credentials"
                ),
                payload=payload,
            )
        if form_root is None:
            return ApplyResult(
                status="failed",
                error=(
                    "linkedin live Easy Apply could not load the application form; "
                    "refresh session cookies and preview with dry_run first"
                ),
                payload=payload,
            )
        missing = payload.get("missing_required_fields") or []
        if missing:
            return ApplyResult(
                status="failed",
                error=(
                    "linkedin Easy Apply has required questions that are not mapped in "
                    f"the application profile: {', '.join(missing)}"
                ),
                payload=payload,
            )

        body = build_submit_body(payload)
        headers = voyager_request_headers(ctx.credentials)
        cookies = voyager_request_cookies(ctx.credentials)
        try:
            response = self.http.post_json(SUBMIT_URL, json=body, headers=headers, cookies=cookies)
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc), payload=payload)

        app_id = _extract_application_id(response)
        return ApplyResult(status="submitted", payload=payload, external_application_id=app_id)

    def _resolve_detail(self, ctx: ApplyContext) -> LinkedInJobDetail:
        override = str(ctx.config.get("external_apply_url") or "").strip()
        if override:
            detail = _detail_from_override(ctx, decode_linkedin_redirect(override))
            return detail

        page_url = resolve_job_posting_url(ctx.job_external_id, ctx.job_url)
        html = self.http.get_text(page_url)
        parsed = parse_job_posting_page(html, fallback_job_id=ctx.job_external_id)
        if parsed is None:
            raise ValueError(
                "linkedin applier could not parse apply metadata from the job posting page; "
                "add session cookies via site credentials or set config.external_apply_url"
            )
        detail = parsed

        if detail.external_apply_url is None and not detail.easy_apply:
            external = fetch_company_apply_url(self.http, detail.job_id, ctx.credentials)
            if external:
                detail = merge_external_apply_url(detail, external)
        return detail


def _detail_from_override(ctx: ApplyContext, external_apply_url: str) -> LinkedInJobDetail:
    """Build a minimal detail record when operators pin the downstream apply URL."""
    return LinkedInJobDetail(
        job_id=ctx.job_external_id,
        title=ctx.job_title,
        company=ctx.company,
        reference_id=None,
        tracking_id=None,
        easy_apply=False,
        offsite_apply=True,
        external_apply_url=external_apply_url,
        expired=False,
    )


def _extract_application_id(response: Any) -> str | None:
    if isinstance(response, dict):
        value = response.get("value")
        if isinstance(value, dict):
            for key in ("applicationId", "application_id", "id", "entityUrn"):
                candidate = value.get(key)
                if candidate is not None:
                    return str(candidate)
        for key in ("applicationId", "application_id", "id"):
            candidate = response.get(key)
            if candidate is not None:
                return str(candidate)
    return None
