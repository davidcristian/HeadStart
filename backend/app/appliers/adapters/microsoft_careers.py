"""Microsoft Careers apply adapter (Eightfold SmartApply).

Microsoft's careers portal uses Eightfold SmartApply public JSON endpoints:
  GET  /api/apply/v2/jobs/<id>
  GET  /api/apply/v2/questions?position_id=<id>
  POST /api/apply/v2/candidate
  POST /api/pcsx/upload_resume
  POST /api/application/v2/submit

Config / context:
  - `config["domain"]`: Eightfold domain slug (default ``microsoft.com``).
  - Credential cookies: logged-in Microsoft Careers session from apply.careers.microsoft.com.
  - Credential `session["csrf_token"]` (optional; fetched from the apply page when omitted).

Use `dry_run=True` to preview the mapped candidate and submit payload without
authentication. Live submit requires the candidate's own logged-in session.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.microsoft_careers_common import (
    apply_page_url,
    candidate_url,
    extract_application_id,
    has_session_cookies,
    job_detail_url,
    questions_url,
    request_headers,
    resolve_csrf_token,
    resolve_domain,
    resolve_position_id,
    submit_url,
    upload_resume_url,
)
from app.appliers.adapters.microsoft_careers_payload import (
    build_answers,
    build_application_payload,
    build_candidate,
    build_resume_upload_body,
    build_submit_body,
)
from app.appliers.base import Applier, register_applier
from app.appliers.types import ApplyContext, ApplyResult
from app.scrapers.http import HttpClient


@register_applier("microsoft_careers")
class MicrosoftCareersApplier(Applier):
    """Submit (or preview) applications on Microsoft Careers."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        domain = resolve_domain(ctx.config)
        position_id = resolve_position_id(ctx.config, ctx.job_url, ctx.job_external_id)
        if not position_id:
            return ApplyResult(
                status="failed",
                error=(
                    "microsoft_careers applier needs a position id from job_external_id, "
                    "config.position_id, or a /careers/job/<id> URL"
                ),
            )

        locale = str(ctx.config.get("hl") or ctx.config.get("locale") or "en")
        apply_url = apply_page_url(position_id)

        try:
            job_detail = self._fetch_job_detail(domain, position_id, locale=locale)
            questions = self._fetch_questions(domain, position_id, locale=locale)
            candidate = build_candidate(
                ctx.profile,
                job_title=ctx.job_title,
                company=ctx.company,
                cover_letter=ctx.cover_letter,
            )
            answers = build_answers(ctx.profile, questions)
            payload = build_application_payload(
                domain=domain,
                position_id=position_id,
                job_detail=job_detail,
                questions=questions,
                candidate=candidate,
                answers=answers,
                resume_file=ctx.resume_file,
                include_resume_bytes=not ctx.dry_run,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc))

        if ctx.dry_run:
            return ApplyResult(status="dry_run", payload=payload)

        http = self.http
        csrf_token = resolve_csrf_token(
            ctx.credentials,
            ctx.config,
            http=http,
            apply_url=apply_url,
        )
        if not csrf_token:
            return ApplyResult(
                status="failed",
                error=(
                    "microsoft_careers live apply requires a CSRF token in "
                    "credential session.csrf_token or an apply page session"
                ),
                payload=payload,
            )
        if not has_session_cookies(ctx.credentials):
            return ApplyResult(
                status="failed",
                error=(
                    "microsoft_careers live apply requires logged-in Microsoft Careers "
                    "session cookies in site credentials"
                ),
                payload=payload,
            )

        headers = request_headers(
            csrf_token=csrf_token,
            referer=apply_url,
            credentials=ctx.credentials,
        )

        try:
            self._save_candidate(
                http, domain, position_id, candidate, headers=headers, locale=locale
            )
            if ctx.resume_file is not None:
                resume_body = build_resume_upload_body(domain=domain, resume_file=ctx.resume_file)
                http.post_json(upload_resume_url(), json=resume_body, headers=headers)
            submit_body = build_submit_body(
                domain=domain,
                position_id=position_id,
                candidate=candidate,
                answers=answers,
            )
            response = http.post_json(
                submit_url(domain, position_id),
                json=submit_body,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc), payload=payload)

        app_id = extract_application_id(response)
        return ApplyResult(
            status="submitted",
            payload=payload,
            external_application_id=app_id,
        )

    def _fetch_job_detail(self, domain: str, position_id: str, *, locale: str) -> dict[str, Any]:
        data = self.http.get_json(job_detail_url(domain, position_id, locale=locale))
        if not isinstance(data, dict):
            raise ValueError("microsoft_careers job detail returned unexpected payload")
        return data

    def _fetch_questions(self, domain: str, position_id: str, *, locale: str) -> dict[str, Any]:
        data = self.http.get_json(questions_url(domain, position_id, locale=locale))
        return data if isinstance(data, dict) else {}

    def _save_candidate(
        self,
        http: HttpClient,
        domain: str,
        position_id: str,
        candidate: dict[str, Any],
        *,
        headers: dict[str, str],
        locale: str,
    ) -> None:
        """Persist candidate contact fields on the SmartApply session."""
        url = candidate_url(domain, position_id, locale=locale)
        http.post_json(url, json=candidate, headers=headers)
