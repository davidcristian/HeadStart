"""Indeed apply adapter.

Indeed listings usually redirect Easy Apply jobs to an employer ATS (Greenhouse,
Lever, Ashby, Workday, Google Careers, Microsoft Careers, Amazon Jobs). This adapter
fetches the public viewjob page, parses embedded `_initialData`, and delegates to
the matching downstream applier when possible. When the posting is hosted on Indeed itself, dry-run
previews the smartapply payload; live submit needs logged-in Indeed session
cookies and posts to smartapply (best-effort — multi-step questionnaires may
still require manual answers in `profile.answers`).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.indeed_detail import (
    IndeedJobDetail,
    parse_viewjob_page,
    resolve_viewjob_url,
)
from app.appliers.adapters.indeed_easy_apply import (
    SMARTAPPLY_SUBMIT_URL,
    build_easy_apply_payload,
    build_submit_body,
    has_indeed_session_cookies,
)
from app.appliers.adapters.indeed_route import resolve_apply_route
from app.appliers.base import Applier, get_applier, register_applier
from app.appliers.types import ApplyContext, ApplyResult
from app.schemas.profile import ResumeFile


@register_applier("indeed")
class IndeedApplier(Applier):
    """Apply to Indeed postings via downstream ATS delegation or smartapply."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        try:
            detail = self._resolve_detail(ctx)
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))

        route = resolve_apply_route(detail)
        if route.kind == "external_ats":
            return self._delegate(ctx, detail, route)
        if route.kind == "indeed_hosted":
            return self._apply_hosted(ctx, detail)
        return ApplyResult(
            status="failed",
            error=route.reason or "indeed posting cannot be auto-applied",
            payload={
                "route": route.kind,
                "external_apply_url": detail.external_apply_url,
                "easily_apply": detail.easily_apply,
            },
        )

    def _delegate(self, ctx: ApplyContext, detail: IndeedJobDetail, route: Any) -> ApplyResult:
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
            "indeed_route": "external_ats",
            "delegated_adapter": route.adapter_key,
            "indeed_job_key": detail.job_key,
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

    def _apply_hosted(self, ctx: ApplyContext, detail: IndeedJobDetail) -> ApplyResult:
        try:
            payload = build_easy_apply_payload(
                detail,
                ctx.profile,
                company=ctx.company,
                job_title=ctx.job_title,
                cover_letter=ctx.cover_letter,
                resume_file=ctx.resume_file,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))

        if ctx.dry_run:
            return ApplyResult(status="dry_run", payload=payload)

        if not has_indeed_session_cookies(ctx.credentials):
            return ApplyResult(
                status="failed",
                error=(
                    "indeed live apply requires logged-in Indeed session cookies "
                    "(e.g. PPID, SOCK) in site credentials"
                ),
                payload=payload,
            )

        body = build_submit_body(payload, resume_file=_resolve_resume_file(ctx))
        headers = _credential_headers(ctx.credentials)
        try:
            response = self.http.post_json(
                SMARTAPPLY_SUBMIT_URL,
                json=body,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc), payload=payload)

        app_id = _extract_application_id(response)
        return ApplyResult(status="submitted", payload=payload, external_application_id=app_id)

    def _resolve_detail(self, ctx: ApplyContext) -> IndeedJobDetail:
        override = str(ctx.config.get("external_apply_url") or "").strip()
        if override:
            detail = _detail_from_override(ctx, override)
            if detail is not None:
                return detail

        page_url = resolve_viewjob_url(ctx.job_external_id, ctx.job_url, ctx.config)
        html = self.http.get_text(page_url)
        detail = parse_viewjob_page(html, fallback_job_key=ctx.job_external_id)
        if detail is None:
            raise ValueError(
                "indeed applier could not parse apply metadata from the viewjob page; "
                "add session cookies via site credentials or set config.external_apply_url"
            )
        return detail


def _detail_from_override(ctx: ApplyContext, external_apply_url: str) -> IndeedJobDetail | None:
    """Build a minimal detail record when operators pin the downstream apply URL."""
    return IndeedJobDetail(
        job_key=ctx.job_external_id,
        title=ctx.job_title,
        company=ctx.company,
        external_apply_url=external_apply_url,
        easily_apply=False,
        indeed_applyable_job_id=None,
        apply_continue_url=None,
        expired=False,
    )


def _credential_headers(credentials: dict[str, dict[str, str]] | None) -> dict[str, str]:
    if not credentials:
        return {}
    headers = dict(credentials.get("headers") or {})
    csrf = (credentials.get("session") or {}).get("csrf_token")
    if csrf:
        headers.setdefault("indeed-co", "US")
        headers["X-Indeed-Csrf-Token"] = str(csrf)
    return headers


def _extract_application_id(response: Any) -> str | None:
    if isinstance(response, dict):
        for key in ("applicationId", "application_id", "id"):
            value = response.get(key)
            if value is not None:
                return str(value)
    return None


def _resolve_resume_file(ctx: ApplyContext) -> ResumeFile | None:
    """Return the stored resume file attached to the apply context, if any."""
    if ctx.resume_file is not None:
        return ctx.resume_file
    profile_resume = getattr(ctx.profile, "resume_file", None)
    return profile_resume if isinstance(profile_resume, ResumeFile) else None
