"""Greenhouse Job Board structured employments and educations mapping."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.appliers.adapters.workday_lookup import match_lookup_item, normalize_lookup_text
from app.appliers.structured_profile import applicable_education, applicable_work_experience
from app.schemas.profile import EducationEntry, ProfileData, WorkExperienceEntry
from app.scrapers.http import HttpClient

GREENHOUSE_SCHOOLS_URL = (
    "https://boards-api.greenhouse.io/v1/boards/{board_token}/education/schools"
)
GREENHOUSE_DEGREES_URL = (
    "https://boards-api.greenhouse.io/v1/boards/{board_token}/education/degrees"
)
GREENHOUSE_DISCIPLINES_URL = (
    "https://boards-api.greenhouse.io/v1/boards/{board_token}/education/disciplines"
)


class GreenhouseEducationResolver:
    """Resolve profile education text to Greenhouse catalog ids when possible."""

    def __init__(
        self,
        http: HttpClient | None,
        board_token: str,
        config: dict[str, Any],
    ) -> None:
        self._http = http
        self._board_token = board_token
        self._config = config
        self._enabled = not config.get("skip_education_lookup")
        self._cache: dict[tuple[str, str], list[dict[str, str]]] = {}

    def resolve_all(self, profile: ProfileData) -> list[dict[str, Any]]:
        """Build Greenhouse education objects for all resolvable profile rows."""
        return [
            education
            for entry in applicable_education(profile)
            if (education := self.resolve_entry(entry)) is not None
        ]

    def resolve_entry(self, entry: EducationEntry) -> dict[str, Any] | None:
        """Map one profile education row to a Greenhouse education object."""
        school_id = self._resolve_id("school", entry.school)
        degree_id = self._resolve_id("degree", entry.degree) or _config_default_id(
            self._config, "default_degree_id"
        )
        discipline_id = self._resolve_id("discipline", entry.field_of_study) or _config_default_id(
            self._config, "default_discipline_id"
        )
        if not school_id or not degree_id or not discipline_id or not entry.start_year:
            return None
        return build_education(
            entry,
            school_name_id=str(school_id),
            degree_id=str(degree_id),
            discipline_id=str(discipline_id),
        )

    def _resolve_id(self, kind: str, value: str) -> str | None:
        stripped = value.strip()
        if not stripped:
            return None
        alias = _config_alias(self._config, kind, stripped)
        if alias:
            return str(alias)
        if stripped.isdigit():
            return stripped
        if not self._enabled or self._http is None:
            return None
        match = match_lookup_item(self._fetch_candidates(kind, stripped), stripped)
        if match and match.get("id"):
            return str(match["id"])
        return None

    def _fetch_candidates(self, kind: str, search_text: str) -> list[dict[str, str]]:
        cache_key = (kind, normalize_lookup_text(search_text))
        if cache_key in self._cache:
            return self._cache[cache_key]

        url = _lookup_url(kind, self._board_token, search_text)
        try:
            data = self._http.get_json(url) if self._http is not None else {}
        except httpx.HTTPError:
            data = {}
        candidates = _parse_greenhouse_items(data)
        self._cache[cache_key] = candidates
        return candidates


def build_employment(entry: WorkExperienceEntry) -> dict[str, Any]:
    """Map a profile work-experience row to a Greenhouse employment object."""
    body: dict[str, Any] = {
        "company_name": entry.company.strip(),
        "title": entry.job_title.strip(),
        "start_date": {
            "month": str(entry.start_month),
            "year": str(entry.start_year),
        },
        "current": "true" if entry.is_current else "false",
    }
    if not entry.is_current and entry.end_year and entry.end_month:
        body["end_date"] = {
            "month": str(entry.end_month),
            "year": str(entry.end_year),
        }
    return body


def build_education(
    entry: EducationEntry,
    *,
    school_name_id: str,
    degree_id: str,
    discipline_id: str,
) -> dict[str, Any]:
    """Map a profile education row to a Greenhouse education object."""
    body: dict[str, Any] = {
        "school_name_id": school_name_id,
        "degree_id": degree_id,
        "discipline_id": discipline_id,
        "start_date": {
            "month": "1",
            "year": str(entry.start_year),
        },
        "end_date": {
            "month": "6",
            "year": str(entry.end_year or entry.start_year),
        },
    }
    return body


def build_employments(profile: ProfileData) -> list[dict[str, Any]]:
    """Greenhouse employment objects for all applicable profile rows."""
    return [build_employment(entry) for entry in applicable_work_experience(profile)]


def build_education_lookup_resolver(
    http: HttpClient | None,
    *,
    board_token: str | None,
    config: dict[str, Any],
) -> GreenhouseEducationResolver | None:
    """Create a resolver when a board token is available."""
    if not board_token:
        return None
    return GreenhouseEducationResolver(http, board_token, config)


def _lookup_url(kind: str, board_token: str, search_text: str) -> str:
    templates = {
        "school": GREENHOUSE_SCHOOLS_URL,
        "degree": GREENHOUSE_DEGREES_URL,
        "discipline": GREENHOUSE_DISCIPLINES_URL,
    }
    template = templates[kind]
    query = urlencode({"term": search_text})
    return f"{template.format(board_token=board_token)}?{query}"


def _parse_greenhouse_items(data: Any) -> list[dict[str, str]]:
    rows = data.get("items") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    parsed: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item_id = row.get("id")
        label = row.get("text")
        if item_id is None or not isinstance(label, str) or not label.strip():
            continue
        parsed.append({"id": str(item_id), "descriptor": label.strip()})
    return parsed


def _config_alias(config: dict[str, Any], kind: str, value: str) -> str | None:
    aliases = config.get("education_id_aliases")
    if not isinstance(aliases, dict):
        return None
    for key in (f"{kind}:{value}", value):
        alias = aliases.get(key)
        if alias:
            return str(alias)
    return None


def _config_default_id(config: dict[str, Any], key: str) -> str | None:
    value = config.get(key)
    return str(value) if value else None
