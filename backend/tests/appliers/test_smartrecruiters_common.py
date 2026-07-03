"""Tests for SmartRecruiters shared helpers."""

import httpx
import pytest

from app.appliers.adapters.smartrecruiters_common import (
    auth_headers,
    parse_company_from_url,
    resolve_access_token,
    resolve_company_id,
    resolve_posting_uuid,
    resolve_smart_token,
    split_name,
)
from tests.conftest import make_http_client


def _client(payload: object) -> object:
    import json

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text=json.dumps(payload), headers={"content-type": "application/json"}
        )

    return make_http_client(handler)


def test_resolve_company_id_from_careers_url() -> None:
    assert (
        resolve_company_id({}, "https://careers.smartrecruiters.com/AcmeCorp/some-slug")
        == "AcmeCorp"
    )


def test_resolve_company_id_from_site_config() -> None:
    assert resolve_company_id({"site": "SiteCorp"}, "") == "SiteCorp"


def test_resolve_posting_uuid_from_config_override() -> None:
    assert (
        resolve_posting_uuid({"posting_uuid": "uuid-1"}, "1", company_id="AcmeCorp", http=None)
        == "uuid-1"
    )


def test_resolve_posting_uuid_requires_company_id() -> None:
    with pytest.raises(ValueError, match="company_id"):
        resolve_posting_uuid({}, "1", company_id=None, http=_client({}))


def test_resolve_posting_uuid_rejects_non_dict_payload() -> None:
    with pytest.raises(ValueError, match="unexpected payload"):
        resolve_posting_uuid({}, "1", company_id="AcmeCorp", http=_client(["x"]))


def test_resolve_posting_uuid_requires_uuid() -> None:
    with pytest.raises(ValueError, match="missing uuid"):
        resolve_posting_uuid({}, "1", company_id="AcmeCorp", http=_client({"name": "x"}))


def test_resolve_smart_token_variants() -> None:
    assert resolve_smart_token({"session": {"smart_token": "t"}}, {}) == "t"
    assert resolve_smart_token({"session": {"smart_token": ""}}, {"smart_token": "c"}) == "c"
    assert resolve_smart_token(None, {}) is None


def test_resolve_access_token_variants() -> None:
    assert resolve_access_token({"session": {"access_token": "a"}}, {}) == "a"
    assert resolve_access_token({"session": {}}, {"access_token": "c"}) == "c"
    assert resolve_access_token(None, {}) is None


def test_auth_headers_falls_back_to_access_token_then_empty() -> None:
    assert auth_headers({"session": {"access_token": "bearer"}}, {}) == {
        "Authorization": "Bearer bearer"
    }
    assert auth_headers(None, {}) == {}


def test_split_name_empty() -> None:
    assert split_name("   ") == ("", "")


def test_parse_company_from_url_variants() -> None:
    assert parse_company_from_url("https://careers.smartrecruiters.com/AcmeCorp/x") == "AcmeCorp"
    assert parse_company_from_url("https://example.com/AcmeCorp") is None
    assert parse_company_from_url("https://jobs.smartrecruiters.com/") is None
