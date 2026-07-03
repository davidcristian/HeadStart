"""Shared helpers for the LinkedIn apply adapter."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

_GUEST_JOB_POSTING_API = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
_JOB_ID_FROM_URL_RE = re.compile(r"-(\d+)(?:\?|$)")
_CODE_COMMENT_RE = re.compile(r"<!--\s*\"?([^\"]+?)\"?\s*-->")


def resolve_job_posting_url(job_external_id: str, job_url: str) -> str:
    """Canonical guest job-posting HTML URL for a scraped LinkedIn listing."""
    job_id = job_external_id.strip() or _job_id_from_url(job_url)
    if job_id:
        return _GUEST_JOB_POSTING_API.format(job_id=job_id)
    raise ValueError("linkedin applier needs a numeric job id or linkedin.com/jobs/view URL")


def extract_code_comment(html: str, element_id: str) -> str | None:
    """Read hidden `<code id="..."><!--value--></code>` values from guest HTML."""
    marker = f'id="{element_id}"'
    idx = html.find(marker)
    if idx == -1:
        return None
    start = html.find("<!--", idx)
    end = html.find("-->", start + 4) if start != -1 else -1
    if start == -1 or end == -1:
        return None
    match = _CODE_COMMENT_RE.search(html[start : end + 3])
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def decode_linkedin_redirect(url: str) -> str:
    """Decode LinkedIn safety redirect URLs to the underlying employer apply link."""
    normalized = url.strip()
    if not normalized:
        return normalized
    parsed = urlparse(normalized)
    if parsed.netloc.lower().endswith("linkedin.com") and "/redir/redirect" in parsed.path:
        target = parse_qs(parsed.query).get("url", [""])[0]
        if target:
            return unquote(target)
    return normalized


def has_linkedin_session_cookies(credentials: dict[str, dict[str, str]] | None) -> bool:
    """True when credential cookies look like a logged-in LinkedIn account."""
    if not credentials:
        return False
    cookies = credentials.get("cookies") or {}
    return bool(cookies.get("li_at")) and bool(cookies.get("JSESSIONID"))


def resolve_csrf_token(credentials: dict[str, dict[str, str]] | None) -> str | None:
    """Resolve LinkedIn CSRF token from credential session or JSESSIONID cookie."""
    if credentials:
        session = credentials.get("session") or {}
        for key in ("csrf_token", "csrf-token", "Csrf-Token"):
            raw = session.get(key)
            if raw and str(raw).strip():
                return str(raw).strip()
        cookies = credentials.get("cookies") or {}
        jsession = str(cookies.get("JSESSIONID") or "").strip().strip('"')
        if jsession:
            return jsession if jsession.startswith("ajax:") else f"ajax:{jsession}"
    return None


def voyager_request_headers(credentials: dict[str, dict[str, str]] | None) -> dict[str, str]:
    """Headers required for authenticated Voyager API calls."""
    headers = {
        "Accept": "application/vnd.linkedin.normalized+json+2.1",
        "x-restli-protocol-version": "2.0.0",
        "x-li-lang": "en_US",
    }
    if credentials:
        headers.update(credentials.get("headers") or {})
    csrf = resolve_csrf_token(credentials)
    if csrf:
        headers["csrf-token"] = csrf
        headers["x-li-graphql-pegasus-client"] = "true"
    return headers


def voyager_request_cookies(credentials: dict[str, dict[str, str]] | None) -> dict[str, str]:
    """Cookie jar for authenticated Voyager API calls."""
    if not credentials:
        return {}
    return dict(credentials.get("cookies") or {})


def build_graphql_variables_string(data: Any) -> str:
    """Serialize GraphQL variables the way LinkedIn's Voyager API expects."""
    if isinstance(data, dict):
        parts = [f"{key}:{build_graphql_variables_string(value)}" for key, value in data.items()]
        return f"({','.join(parts)})"
    if isinstance(data, list):
        parts = [build_graphql_variables_string(item) for item in data]
        return f"List({','.join(parts)})"
    if isinstance(data, bool):
        return "true" if data else "false"
    if isinstance(data, str):
        from urllib.parse import quote

        return quote(data, safe="")
    return str(data)


def build_graphql_url(
    *,
    query_id: str,
    variables: dict[str, Any],
    query_name: str | None = None,
) -> str:
    """Build a Voyager GraphQL URL."""
    variables_str = build_graphql_variables_string(variables)
    params = [f"variables={variables_str}", f"queryId={query_id}"]
    if query_name:
        params.append(f"queryName={query_name}")
    return f"https://www.linkedin.com/voyager/api/graphql?{'&'.join(params)}"


def _job_id_from_url(job_url: str) -> str:
    match = _JOB_ID_FROM_URL_RE.search(job_url or "")
    return match.group(1) if match else ""
