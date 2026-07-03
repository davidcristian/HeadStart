"""Shared LinkedIn Easy Apply form parsing helpers."""

from __future__ import annotations

from typing import Any


def extract_form_root(form_payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first Easy Apply form object from a Voyager GraphQL payload."""
    data = form_payload.get("data")
    if not isinstance(data, dict):
        return None
    container = data.get("jobsDashOnsiteApplyApplicationByJobPosting")
    if not isinstance(container, dict):
        return None
    elements = container.get("elements")
    if not isinstance(elements, list) or not elements:
        return None
    first = elements[0]
    if not isinstance(first, dict):
        return None
    forms = first.get("jobApplicationForms")
    if not isinstance(forms, list) or not forms:
        return None
    form = forms[0]
    return form if isinstance(form, dict) else None


def iter_form_elements(form_root: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten Easy Apply form elements from a form root object."""
    elements: list[dict[str, Any]] = []
    for grouping in form_root.get("questionGroupings") or []:
        if not isinstance(grouping, dict):
            continue
        section = grouping.get("formSection")
        if not isinstance(section, dict):
            continue
        for group in section.get("formElementGroups") or []:
            if not isinstance(group, dict):
                continue
            for element in group.get("formElements") or []:
                if isinstance(element, dict):
                    elements.append(element)
    return elements


def element_title(element: dict[str, Any]) -> str:
    """Best-effort label for a form element."""
    title = element.get("title")
    if isinstance(title, dict):
        text = title.get("text")
        if isinstance(text, str):
            return text.strip()
    return ""


def is_file_upload_element(element: dict[str, Any]) -> bool:
    """True when an Easy Apply form element expects a document upload."""
    component = element.get("formComponentResolutionResult")
    if not isinstance(component, dict):
        return False
    return any(
        key in component
        for key in (
            "documentUploadFormComponent",
            "fileUploadFormComponent",
            "mediaUploadFormComponent",
        )
    )


def build_file_upload_responses(
    form_payload: dict[str, Any],
    *,
    asset_urn: str,
    filename: str,
) -> list[dict[str, Any]]:
    """Map uploaded resume URNs onto file-upload form elements."""
    responses: list[dict[str, Any]] = []
    for element in iter_form_elements(form_payload):
        if not is_file_upload_element(element):
            continue
        urn = str(element.get("entityUrn") or element.get("urn") or "").strip()
        if not urn:
            continue
        responses.append(
            {
                "formElementUrn": urn,
                "formElementInputValues": [
                    {
                        "fileUploadInputValue": {
                            "assetUrn": asset_urn,
                            "fileName": filename,
                        }
                    }
                ],
            }
        )
    return responses


def required_file_upload_titles(form_payload: dict[str, Any]) -> list[str]:
    """Return titles of required file-upload questions on the Easy Apply form."""
    missing: list[str] = []
    for element in iter_form_elements(form_payload):
        if not is_file_upload_element(element) or not bool(element.get("required")):
            continue
        title = element_title(element)
        missing.append(title or str(element.get("entityUrn") or "file upload"))
    return missing


def form_has_file_upload_elements(form_payload: dict[str, Any]) -> bool:
    """True when the Easy Apply form includes at least one file-upload field."""
    return any(is_file_upload_element(element) for element in iter_form_elements(form_payload))
