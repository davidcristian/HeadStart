"""Tests for SmartRecruiters configuration parsing."""

import httpx
import pytest

from app.appliers.adapters.smartrecruiters_configuration import (
    configuration_questions,
    consent_decisions,
    fetch_configuration,
    required_question_ids,
)
from tests.conftest import make_http_client


def _client(payload: object, capture: dict | None = None) -> object:
    import json

    def handler(request: httpx.Request) -> httpx.Response:
        if capture is not None:
            capture["url"] = str(request.url)
        return httpx.Response(
            200, text=json.dumps(payload), headers={"content-type": "application/json"}
        )

    return make_http_client(handler)


def test_fetch_configuration_includes_conditionals_param() -> None:
    capture: dict = {}
    fetch_configuration(
        _client({"questions": []}, capture),
        "uuid-1",
        headers={"X-SmartToken": "t"},
        conditionals_included=True,
    )
    assert "conditionalsIncluded=true" in capture["url"]


def test_fetch_configuration_rejects_non_dict_payload() -> None:
    with pytest.raises(ValueError, match="unexpected payload"):
        fetch_configuration(_client(["x"]), "uuid-1", headers={})


def test_consent_decisions_separated_model_with_scopes() -> None:
    configuration = {
        "settings": {
            "consentSettings": {
                "consentModel": "SEPARATED",
                "dataScopes": [{"id": "scope-1"}, {"id": "scope-2"}, {"no_id": True}, "bad"],
            }
        }
    }
    result = consent_decisions(configuration, {"gdpr_consent": False})
    assert result == {"scope-1": False, "scope-2": False}


def test_consent_decisions_settings_not_dict() -> None:
    assert consent_decisions({"settings": "nope"}, {}) is None


def test_consent_decisions_consent_settings_not_dict() -> None:
    assert consent_decisions({"settings": {"consentSettings": "nope"}}, {}) is None


def test_consent_decisions_separated_without_scopes_falls_back_to_single() -> None:
    configuration = {
        "settings": {"consentSettings": {"consentModel": "SEPARATED", "dataScopes": []}}
    }
    assert consent_decisions(configuration, {"gdpr_consent": True}) == {"SINGLE": True}


def test_consent_decisions_empty_consent_settings_falls_back_to_config() -> None:
    # consentSettings is an empty dict: not SEPARATED, not SINGLE, and falsy, so
    # the branch falls through to the config-driven defaults below.
    configuration = {"settings": {"consentSettings": {}}}
    assert consent_decisions(configuration, {"gdpr_consent": True}) == {"SINGLE": True}
    assert consent_decisions({"settings": {"consentSettings": {}}}, {}) is None


def test_consent_decisions_single_when_consent_settings_present() -> None:
    configuration = {"settings": {"consentSettings": {"consentModel": "OTHER"}}}
    assert consent_decisions(configuration, {"gdpr_consent": True}) == {"SINGLE": True}


def test_consent_decisions_from_config_true() -> None:
    assert consent_decisions(None, {"gdpr_consent": True}) == {"SINGLE": True}


def test_consent_decisions_from_config_false() -> None:
    assert consent_decisions(None, {"gdpr_consent": False}) == {"SINGLE": False}


def test_consent_decisions_none_when_unspecified() -> None:
    assert consent_decisions(None, {}) is None


def test_configuration_questions_variants() -> None:
    assert configuration_questions(None) == []
    assert configuration_questions({"questions": "nope"}) == []
    assert configuration_questions({"questions": [{"id": "q"}, "bad"]}) == [{"id": "q"}]


def test_required_question_ids_skips_questions_without_id_or_fields() -> None:
    configuration = {
        "questions": [
            {"label": "no id"},
            {"id": "q1", "fields": "nope"},
            {"id": "q2", "fields": [{"required": True, "type": "TEXT"}]},
            {"id": "q3", "fields": [{"required": True, "type": "INFORMATION"}]},
            {"id": "q4", "fields": [{"required": False, "type": "TEXT"}]},
        ]
    }
    assert required_question_ids(configuration) == ["q2"]
