"""Phenom-hosted partner Apply API live / dry-run helpers."""

from __future__ import annotations

import json

import httpx

from app.appliers.adapters.phenom_common import (
    applications_url,
    extract_application_id,
    extract_error_message,
    resolve_access_token,
)
from app.appliers.adapters.phenom_detail import PhenomJobDetail
from app.appliers.adapters.phenom_payload import (
    build_application_payload,
    build_dry_run_payload,
    custom_fields_from_answers,
)
from app.appliers.types import ApplyContext, ApplyResult
from app.scrapers.http import HttpClient


def apply_hosted(
    http: HttpClient,
    ctx: ApplyContext,
    detail: PhenomJobDetail,
    *,
    careers_base: str | None,
    locale: str,
) -> ApplyResult:
    """Preview or submit via ``POST /apply/v2/applications``."""
    applicant_source = str(ctx.config.get("applicant_source") or "HeadStart").strip()
    custom = custom_fields_from_answers(ctx.profile.answers)
    try:
        application = build_application_payload(
            ctx.profile,
            job_id=detail.job_id,
            applicant_source=applicant_source or "HeadStart",
            resume_file=ctx.resume_file,
            include_resume_bytes=False,
            custom_fields=custom or None,
        )
    except ValueError as exc:
        return ApplyResult(status="failed", error=str(exc))

    preview = build_dry_run_payload(
        application=application,
        detail=detail,
        careers_base_url=careers_base,
        route="phenom_hosted",
    )
    if ctx.dry_run:
        return ApplyResult(status="dry_run", payload=preview)

    token = resolve_access_token(ctx.credentials, ctx.config)
    if not token:
        return ApplyResult(
            status="failed",
            error=(
                "phenom live apply requires partner OAuth access_token in "
                "credential session.access_token (public careers apply varies "
                "by tenant; use Apply API credentials or config.apply_url "
                "delegation to a supported ATS)"
            ),
            payload=preview,
        )

    live_application = build_application_payload(
        ctx.profile,
        job_id=detail.job_id,
        applicant_source=applicant_source or "HeadStart",
        resume_file=ctx.resume_file,
        include_resume_bytes=True,
        custom_fields=custom or None,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "locale": locale,
        "siteType": "external",
    }
    try:
        resp = http.post_raw(
            applications_url(ctx.config),
            content=json.dumps(live_application).encode("utf-8"),
            headers=headers,
        )
    except httpx.HTTPError as exc:
        return ApplyResult(
            status="failed",
            error=_http_error_message(exc),
            payload=preview,
        )

    body = _response_json(resp)
    if _response_reports_error(body):
        message = extract_error_message(body) or f"HTTP {resp.status_code}"
        return ApplyResult(
            status="failed",
            error=message,
            payload={**preview, "response": body},
        )

    live_payload = {**preview, "response": body}
    if ctx.resume_file is not None:
        live_payload["application"] = {
            **application,
            "resumeData": {
                "fileName": ctx.resume_file.filename,
                "contentTypeId": ctx.resume_file.content_type,
                "size_bytes": ctx.resume_file.size_bytes,
                "uploaded": True,
            },
        }
    return ApplyResult(
        status="submitted",
        payload=live_payload,
        external_application_id=extract_application_id(body),
    )


def _response_json(resp: httpx.Response) -> object:
    try:
        return resp.json()
    except ValueError:
        text = (resp.text or "").strip()
        return text or None


def _response_reports_error(body: object) -> bool:
    if not isinstance(body, dict):
        return False
    status = str(body.get("status") or "").strip().lower()
    if status in {"error", "failed", "failure"}:
        return True
    code = body.get("statusCode")
    if isinstance(code, int) and code >= 400:
        return True
    return isinstance(code, str) and code.strip().isdigit() and int(code.strip()) >= 400


def _http_error_message(exc: httpx.HTTPError) -> str:
    response = getattr(exc, "response", None)
    if response is None:
        return str(exc)
    try:
        data = response.json()
    except ValueError:
        data = None
    message = extract_error_message(data) if data is not None else None
    if message:
        return message
    text = (response.text or "").strip()
    if text:
        return text[:500]
    return str(exc)
