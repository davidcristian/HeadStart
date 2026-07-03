"""SmartRecruiters application configuration parsing."""

from __future__ import annotations

from typing import Any

from app.appliers.adapters.smartrecruiters_common import CONFIGURATION_URL
from app.scrapers.http import HttpClient


def fetch_configuration(
    http: HttpClient,
    posting_uuid: str,
    *,
    headers: dict[str, str],
    conditionals_included: bool = False,
) -> dict[str, Any]:
    """Load screening questions and consent settings for a posting."""
    params: dict[str, str | bool] = {}
    if conditionals_included:
        params["conditionalsIncluded"] = True
    url = CONFIGURATION_URL.format(posting_uuid=posting_uuid)
    data = http.get_json(url, headers=headers, params=params or None)
    if not isinstance(data, dict):
        raise ValueError("smartrecruiters configuration returned unexpected payload")
    return data


def consent_decisions(
    configuration: dict[str, Any] | None,
    config: dict[str, Any],
) -> dict[str, bool] | None:
    """Build consentDecisions from posting configuration or source defaults."""
    if configuration:
        settings = configuration.get("settings")
        if isinstance(settings, dict):
            consent_settings = settings.get("consentSettings")
            if isinstance(consent_settings, dict):
                model = str(consent_settings.get("consentModel") or "").upper()
                if model == "SEPARATED":
                    scopes = consent_settings.get("dataScopes")
                    if isinstance(scopes, list) and scopes:
                        granted = bool(config.get("gdpr_consent", True))
                        return {
                            str(scope.get("id") or scope): granted
                            for scope in scopes
                            if isinstance(scope, dict) and scope.get("id")
                        }
                if model == "SINGLE" or consent_settings:
                    return {"SINGLE": bool(config.get("gdpr_consent", True))}

    if config.get("gdpr_consent"):
        return {"SINGLE": True}
    if config.get("gdpr_consent") is False:
        return {"SINGLE": False}
    return None


def configuration_questions(configuration: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Screening questions from a configuration payload."""
    if not configuration:
        return []
    questions = configuration.get("questions")
    if not isinstance(questions, list):
        return []
    return [question for question in questions if isinstance(question, dict)]


def required_question_ids(configuration: dict[str, Any] | None) -> list[str]:
    """Question ids that must have answers before live submit."""
    required: list[str] = []
    for question in configuration_questions(configuration):
        question_id = question.get("id")
        if not question_id:
            continue
        fields = question.get("fields")
        if not isinstance(fields, list):
            continue
        if any(
            isinstance(field, dict)
            and field.get("required")
            and field.get("type") not in {"INFORMATION"}
            for field in fields
        ):
            required.append(str(question_id))
    return required
