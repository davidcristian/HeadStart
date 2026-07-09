"""Unit tests for shared hosted-submit post-2xx error helpers."""

from __future__ import annotations

from app.appliers.adapters.hosted_submit_response import (
    extract_error_message,
    response_has_error,
)


def _id_from_top(response: object) -> str | None:
    if isinstance(response, dict) and response.get("applicationId") is not None:
        return str(response["applicationId"])
    return None


def test_response_has_error_variants() -> None:
    assert response_has_error("nope", extract_application_id=_id_from_top) is False
    assert response_has_error({"success": True}, extract_application_id=_id_from_top) is False
    assert response_has_error({"success": False}, extract_application_id=_id_from_top) is True
    assert response_has_error({"error": "boom"}, extract_application_id=_id_from_top) is True
    assert response_has_error({"errors": ["x"]}, extract_application_id=_id_from_top) is True
    assert (
        response_has_error({"message": "rate limited"}, extract_application_id=_id_from_top) is True
    )
    assert (
        response_has_error(
            {"message": "ok", "applicationId": "a-1"},
            extract_application_id=_id_from_top,
        )
        is False
    )


def test_extract_error_message_variants() -> None:
    default = "apply rejected the submission"
    assert extract_error_message({"error": " boom "}, default=default) == "boom"
    assert extract_error_message({"errors": ["a", {"message": "b"}]}, default=default) == "a; b"
    assert extract_error_message({"errors": "flat error"}, default=default) == "flat error"
    assert extract_error_message({"message": " soft fail "}, default=default) == "soft fail"
    assert extract_error_message({}, default=default) == default
    assert extract_error_message("nope", default=default) == default
