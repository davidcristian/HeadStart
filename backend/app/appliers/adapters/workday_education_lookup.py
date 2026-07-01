"""Workday CXS degree and field-of-study lookup resolution."""

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
from app.schemas.profile import EducationEntry
from app.scrapers.http import HttpClient

_DEGREE_KIND = "degree"
_FIELD_KIND = "fieldOfStudy"


class EducationLookupResolver:
    """Resolve profile education text to tenant catalog ids when possible."""

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
        self._enabled = not config.get("skip_education_lookup")
        self._cache: dict[tuple[str, str], list[dict[str, str]]] = {}

    def degree_reference(self, value: str) -> dict[str, str] | None:
        """CXS degree reference for one profile value."""
        return self._resolve_reference(_DEGREE_KIND, value)

    def field_of_study_reference(self, value: str) -> dict[str, str] | None:
        """CXS field-of-study reference for one profile value."""
        return self._resolve_reference(_FIELD_KIND, value)

    def references_for(
        self, entry: EducationEntry
    ) -> tuple[dict[str, str] | None, dict[str, str] | None]:
        """Resolved degree and field-of-study references for one education row."""
        degree = self.degree_reference(entry.degree)
        field = self.field_of_study_reference(entry.field_of_study)
        return degree, field

    def _resolve_reference(self, kind: str, value: str) -> dict[str, str] | None:
        stripped = value.strip()
        if not stripped:
            return None
        alias = _config_alias(self._config, kind, stripped)
        if alias:
            return {"id": alias} if is_workday_id(alias) else {"descriptor": alias}
        if is_workday_id(stripped):
            return {"id": stripped}
        if not self._enabled:
            return {"descriptor": stripped}
        candidates = self._fetch_candidates(kind, stripped)
        match = match_lookup_item(candidates, stripped)
        return workday_reference(stripped, match)

    def _fetch_candidates(self, kind: str, search_text: str) -> list[dict[str, str]]:
        cache_key = (kind, normalize_lookup_text(search_text))
        if cache_key in self._cache:
            return self._cache[cache_key]

        query = urlencode({"searchText": search_text})
        url = f"{self._target.api_base()}/institutionvalues/{kind}?{query}"
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


def build_education_lookup_resolver(
    http: HttpClient | None,
    *,
    target: WorkdayTarget | None,
    job_path: str,
    config: dict[str, Any] | None,
    csrf_token: str | None,
    session_id: str | None,
    credentials: dict[str, dict[str, str]] | None,
) -> EducationLookupResolver | None:
    """Create a resolver when lookup prerequisites are available."""
    if http is None or target is None:
        return None
    if not credentials and not csrf_token:
        return None
    return EducationLookupResolver(
        http,
        target=target,
        job_path=job_path,
        config=config or {},
        csrf_token=csrf_token,
        session_id=session_id,
        credentials=credentials,
    )


def _config_alias(config: dict[str, Any], kind: str, value: str) -> str | None:
    """Optional config override for a specific degree or field label."""
    aliases = config.get("education_lookup_aliases")
    if not isinstance(aliases, dict):
        return None
    for key in (f"{kind}:{value}", f"{kind}:{normalize_lookup_text(value)}", value):
        alias = aliases.get(key)
        if alias:
            return str(alias)
    return None
