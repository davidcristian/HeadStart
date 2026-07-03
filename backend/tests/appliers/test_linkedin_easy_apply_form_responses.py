"""Unit tests for LinkedIn Easy Apply form-response builders."""

from __future__ import annotations

from app.appliers.adapters.linkedin_easy_apply import build_form_responses
from app.schemas.profile import ProfileData


def _profile(**overrides: object) -> ProfileData:
    base: dict[str, object] = {
        "full_name": "Ada Lovelace",
        "email": "ada@example.com",
        "phone": "+1 555 0100",
        "location": "Remote",
        "resume_text": "Experienced engineer.",
        "cover_letter_template": "Dear {company}, excited about {job_title}.",
    }
    base.update(overrides)
    return ProfileData(**base)


def _form_root(elements: list[dict[str, object]]) -> dict[str, object]:
    return {
        "questionGroupings": [{"formSection": {"formElementGroups": [{"formElements": elements}]}}]
    }


def _text_el(urn: str, title: str) -> dict[str, object]:
    return {
        "entityUrn": urn,
        "title": {"text": title},
        "formComponentResolutionResult": {"singleLineTextFormComponent": {}},
    }


def test_build_form_responses_skips_urnless_and_file_upload() -> None:
    form_root = _form_root(
        [
            {"title": {"text": "no urn"}},  # skipped - no urn
            {
                "entityUrn": "urn:file",
                "title": {"text": "Resume"},
                "formComponentResolutionResult": {"documentUploadFormComponent": {}},
            },  # skipped - file upload
            {
                "entityUrn": "urn:email",
                "title": {"text": "Email address"},
                "formComponentResolutionResult": {"singleLineTextFormComponent": {}},
            },
        ]
    )
    responses, missing = build_form_responses(form_root, _profile(), cover_letter=None)
    assert [r["formElementUrn"] for r in responses] == ["urn:email"]
    assert missing == []


def test_build_form_responses_answers_by_urn_and_label() -> None:
    form_root = _form_root(
        [
            {
                "required": True,
                "entityUrn": "urn:custom",
                "title": {"text": "Years of experience"},
                "formComponentResolutionResult": {"multilineTextFormComponent": {}},
            }
        ]
    )
    profile = _profile(answers={"urn:custom": "10"})
    responses, missing = build_form_responses(form_root, profile, cover_letter=None)
    assert responses[0]["formElementInputValues"][0] == {"textInputValue": "10"}
    assert missing == []


def test_build_form_responses_missing_required_label_fallback() -> None:
    form_root = _form_root(
        [
            {
                "required": True,
                "entityUrn": "urn:blank",
                "title": {},  # no text -> title empty, falls back to urn
                "formComponentResolutionResult": {"singleLineTextFormComponent": {}},
            }
        ]
    )
    responses, missing = build_form_responses(form_root, _profile(), cover_letter=None)
    assert responses == []
    assert missing == ["urn:blank"]


def test_build_form_responses_value_for_all_labels() -> None:
    form_root = _form_root(
        [
            _text_el("urn:first", "First name"),
            _text_el("urn:last", "Last name"),
            _text_el("urn:phone", "Mobile phone"),
            _text_el("urn:city", "City"),
            _text_el("urn:cover", "Cover letter"),
        ]
    )
    responses, _ = build_form_responses(form_root, _profile(), cover_letter="Please hire me")
    by_urn = {r["formElementUrn"]: r["formElementInputValues"][0] for r in responses}
    assert by_urn["urn:first"] == {"textInputValue": "Ada"}
    assert by_urn["urn:last"] == {"textInputValue": "Lovelace"}
    assert by_urn["urn:phone"] == {"textInputValue": "+1 555 0100"}
    assert by_urn["urn:city"] == {"textInputValue": "Remote"}
    assert by_urn["urn:cover"] == {"textInputValue": "Please hire me"}


def test_build_form_responses_input_value_without_component() -> None:
    form_root = _form_root(
        [
            {
                "entityUrn": "urn:email",
                "title": {"text": "Email address"},
                # no formComponentResolutionResult -> default textInputValue path
            }
        ]
    )
    responses, _ = build_form_responses(form_root, _profile(), cover_letter=None)
    assert responses[0]["formElementInputValues"][0] == {"textInputValue": "ada@example.com"}


def test_build_form_responses_optional_empty_not_missing() -> None:
    form_root = _form_root(
        [
            {
                "required": False,
                "entityUrn": "urn:opt",
                "title": {"text": "Optional note"},
                "formComponentResolutionResult": {"singleLineTextFormComponent": {}},
            }
        ]
    )
    responses, missing = build_form_responses(form_root, _profile(), cover_letter=None)
    assert responses == []
    assert missing == []


def test_build_form_responses_unknown_component_defaults_text() -> None:
    form_root = _form_root(
        [
            {
                "entityUrn": "urn:email",
                "title": {"text": "Email address"},
                "formComponentResolutionResult": {"someOtherComponent": {}},
            }
        ]
    )
    responses, _ = build_form_responses(form_root, _profile(), cover_letter=None)
    assert responses[0]["formElementInputValues"][0] == {"textInputValue": "ada@example.com"}
