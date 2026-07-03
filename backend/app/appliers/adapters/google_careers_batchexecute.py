"""Google Careers batchexecute RPC transport helpers."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlencode

from app.scrapers.http import HttpClient

BATCHEXECUTE_URL = (
    "https://www.google.com/about/careers/applications/_/HiringCportalFrontendUi/data/batchexecute"
)
_WIZ_DATA_RE = re.compile(r"window\.WIZ_global_data\s*=\s*(\{.*?\});", re.DOTALL)

# RPC ids from HiringCportalFrontendUi (verify after frontend deploys).
RPC_CREATE_PACKET = "tBY1Qe"
RPC_SAVE_PACKET = "o6YK3"
RPC_SUBMIT_PACKET = "pmtdJd"
RPC_SAVE_PROFILE = "qvYBjf"


class GoogleCareersRpcError(RuntimeError):
    """Raised when a batchexecute RPC returns an error envelope."""


def extract_wiz_data(html: str) -> dict[str, Any]:
    """Parse `window.WIZ_global_data` from a careers HTML page."""
    match = _WIZ_DATA_RE.search(html)
    if not match:
        raise ValueError("google_careers page is missing WIZ_global_data")
    data = json.loads(match.group(1))
    return data


def build_f_req(rpc_id: str, args: Any) -> str:
    """Encode one RPC call into the batchexecute `f.req` form field."""
    args_json = json.dumps(args, separators=(",", ":"), ensure_ascii=False)
    envelope = [[rpc_id, args_json, None, "generic"]]
    return json.dumps([envelope], separators=(",", ":"), ensure_ascii=False)


def strip_xssi(text: str) -> str:
    """Remove Google's anti-XSSI prefix from batchexecute responses."""
    if text.startswith(")]}'"):
        return text[4:].lstrip()
    return text.lstrip()


def parse_batchexecute_response(text: str) -> Any:
    """Parse a batchexecute response body into JSON."""
    cleaned = strip_xssi(text)
    for line in reversed(cleaned.splitlines()):
        candidate = line.strip()
        if candidate.startswith("["):
            return json.loads(candidate)
    return json.loads(cleaned)


def rpc_error_message(payload: Any) -> str | None:
    """Return a human-readable RPC error when the envelope reports failure."""
    if not isinstance(payload, list):
        return None
    for item in payload:
        if not isinstance(item, list) or len(item) < 8:
            continue
        if item[0] == "er":
            return str(item[5] or item[3] or "google_careers RPC failed")
    return None


def extract_rpc_result(payload: Any, rpc_id: str) -> Any:
    """Return the decoded payload for a specific rpc id from a batchexecute body."""
    if not isinstance(payload, list):
        raise GoogleCareersRpcError("google_careers RPC response was not a list")
    error = rpc_error_message(payload)
    if error:
        raise GoogleCareersRpcError(error)
    for item in payload:
        if not isinstance(item, list) or len(item) < 3:
            continue
        if item[0] != "wrb.fr" or item[1] != rpc_id:
            continue
        raw = item[2]
        if isinstance(raw, str):
            return json.loads(raw)
        return raw
    raise GoogleCareersRpcError(f"google_careers RPC {rpc_id} missing from response")


def call_batchexecute(
    http: HttpClient,
    *,
    rpc_id: str,
    args: Any,
    wiz: dict[str, Any],
    at_token: str,
    source_path: str,
    req_id: int = 100001,
    extra_headers: dict[str, str] | None = None,
) -> Any:
    """Invoke one HiringCportalFrontendUi batchexecute RPC."""
    params = {
        "rpcids": rpc_id,
        "source-path": source_path,
        "bl": str(wiz.get("cfb2h") or ""),
        "hl": "en",
        "rt": "c",
        "_reqid": str(req_id),
    }
    f_sid = wiz.get("FdrFJe")
    if f_sid is not None:
        params["f.sid"] = str(f_sid)

    headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Origin": "https://www.google.com",
        "Referer": f"https://www.google.com{source_path}",
        **(extra_headers or {}),
    }
    data = {
        "f.req": build_f_req(rpc_id, args),
        "at": at_token,
    }
    url = f"{BATCHEXECUTE_URL}?{urlencode(params)}"
    raw = http.post_form(url, data=data, headers=headers)
    payload = parse_batchexecute_response(raw)
    return extract_rpc_result(payload, rpc_id)
