"""Live Meta Careers application submission helpers."""

from __future__ import annotations

from typing import Any

from app.appliers.adapters.meta_careers_common import (
    SUBMIT_DOC_ID,
    SUBMIT_MUTATION,
    apply_url,
    extract_application_id,
)
from app.appliers.adapters.meta_careers_graphql import (
    fetch_lsd_token,
    post_graphql,
    post_graphql_multipart,
)
from app.schemas.profile import ResumeFile
from app.scrapers.http import HttpClient


def submit_application(
    http: HttpClient,
    *,
    submit_input: dict[str, Any],
    lsd: str,
    credentials: dict[str, dict[str, str]] | None,
    resume_file: ResumeFile | None,
    requisition_id: str,
) -> dict[str, Any]:
    """POST Meta's xcp_create_application_v2 mutation and return the parsed response."""
    variables = {"input": submit_input}
    if resume_file is None:
        return post_graphql(
            http,
            lsd=lsd,
            friendly_name=SUBMIT_MUTATION,
            doc_id=SUBMIT_DOC_ID,
            variables=variables,
            credentials=credentials,
            referer=apply_url(requisition_id),
        )

    uploadables = {
        "candidateResumeFile": (
            resume_file.filename,
            resume_file.data,
            resume_file.content_type,
        )
    }
    return post_graphql_multipart(
        http,
        lsd=lsd,
        friendly_name=SUBMIT_MUTATION,
        doc_id=SUBMIT_DOC_ID,
        variables=variables,
        uploadables=uploadables,
        credentials=credentials,
        referer=apply_url(requisition_id),
    )


def resolve_lsd_token(
    http: HttpClient,
    credentials: dict[str, dict[str, str]] | None,
    config: dict[str, Any],
    *,
    requisition_id: str,
) -> str:
    """Return an lsd token from credentials or by loading the apply page."""
    if credentials:
        session = credentials.get("session") or {}
        for key in ("lsd", "csrf_token"):
            value = session.get(key)
            if value:
                return str(value)
    for key in ("lsd", "csrf_token"):
        value = config.get(key)
        if value:
            return str(value)
    return fetch_lsd_token(http, apply_url(requisition_id))


def external_application_id(response: dict[str, Any]) -> str | None:
    """Best-effort application id from a submit response."""
    return extract_application_id(response)
