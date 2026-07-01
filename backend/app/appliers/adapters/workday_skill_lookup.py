"""Workday CXS skill catalog lookup resolution."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.appliers.adapters.workday_common import WorkdayTarget, request_headers
from app.appliers.adapters.workday_lookup import (
    is_workday_id,
    match_lookup_item,
    normalize_lookup_text,
    parse_lookup_items,
    workday_reference,
)
from app.scrapers.http import HttpClient

_SKILL_KIND = "skill"


class SkillLookupResolver:
    """Resolve profile skill names to tenant catalog ids when possible."""

    def __init__(
        self,
        http: HttpClient,
        *,
        target: WorkdayTarget,
        job_path: str,
        config: dict[str, Any],
        csrf_token: str | None,
        session_id: str | None,
        credentials: dict[str, dict[str, str]] | None,
    ) -> None:
        self._http = http
        self._target = target
        self._job_path = job_path
        self._config = config
        self._csrf_token = csrf_token
        self._session_id = session_id
        self._credentials = credentials
        self._enabled = not config.get("skip_skill_lookup")
        self._cache: dict[str, list[dict[str, str]]] = {}

    def skill_reference(self, value: str) -> dict[str, str] | None:
        """CXS skill reference for one profile skill name."""
        stripped = value.strip()
        if not stripped:
            return None
        alias = _config_alias(self._config, stripped)
        if alias:
            return {"id": alias} if is_workday_id(alias) else {"descriptor": alias}
        if is_workday_id(stripped):
            return {"id": stripped}
        if not self._enabled:
            return {"descriptor": stripped}
        candidates = self._fetch_candidates(stripped)
        match = match_lookup_item(candidates, stripped)
        return workday_reference(stripped, match)

    def _fetch_candidates(self, search_text: str) -> list[dict[str, str]]:
        cache_key = normalize_lookup_text(search_text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        query = urlencode({"searchText": search_text})
        url = f"{self._target.api_base()}/institutionvalues/{_SKILL_KIND}?{query}"
        headers = request_headers(
            self._target,
            self._job_path,
            csrf_token=self._csrf_token,
            session_id=self._session_id,
            credentials=self._credentials,
        )
        try:
            data = self._http.get_json(url, headers=headers)
        except httpx.HTTPError:
            self._cache[cache_key] = []
            return []
        candidates = parse_lookup_items(data)
        self._cache[cache_key] = candidates
        return candidates


def build_skill_lookup_resolver(
    http: HttpClient | None,
    *,
    target: WorkdayTarget | None,
    job_path: str,
    config: dict[str, Any] | None,
    csrf_token: str | None,
    session_id: str | None,
    credentials: dict[str, dict[str, str]] | None,
) -> SkillLookupResolver | None:
    """Create a resolver when lookup prerequisites are available."""
    if http is None or target is None:
        return None
    if not credentials and not csrf_token:
        return None
    return SkillLookupResolver(
        http,
        target=target,
        job_path=job_path,
        config=config or {},
        csrf_token=csrf_token,
        session_id=session_id,
        credentials=credentials,
    )


def _config_alias(config: dict[str, Any], value: str) -> str | None:
    """Optional config override for a specific skill label."""
    aliases = config.get("skill_lookup_aliases")
    if not isinstance(aliases, dict):
        return None
    for key in (value, normalize_lookup_text(value)):
        alias = aliases.get(key)
        if alias:
            return str(alias)
    return None
