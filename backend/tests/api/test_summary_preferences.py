"""API tests for per-user summary provider preferences."""

from fastapi.testclient import TestClient

from tests.api.test_plan_limits import _user_headers_with_plan


def test_summary_preferences_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/summary-preferences").status_code == 401


def test_free_user_can_read_but_not_update_summary_preferences(client: TestClient) -> None:
    headers = _user_headers_with_plan(client, "summary-free@example.com", "free")
    resp = client.get("/api/v1/summary-preferences", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["effective_provider"] == "heuristic"
    assert len(body["providers"]) == 4

    blocked = client.patch(
        "/api/v1/summary-preferences",
        json={"provider": "openai"},
        headers=headers,
    )
    assert blocked.status_code == 402
    assert blocked.json()["code"] == "feature_ai_summaries"


def test_pro_user_updates_summary_provider(client: TestClient) -> None:
    headers = _user_headers_with_plan(client, "summary-pro@example.com", "pro")

    updated = client.patch(
        "/api/v1/summary-preferences",
        json={"provider": "gemini", "api_key": "user-gemini-key"},
        headers=headers,
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["enabled"] is True
    assert body["selected_provider"] == "gemini"
    assert body["effective_provider"] == "gemini"
    assert body["has_custom_api_key"] is True

    cleared = client.patch(
        "/api/v1/summary-preferences",
        json={"provider": None, "api_key": ""},
        headers=headers,
    )
    assert cleared.status_code == 200
    cleared_body = cleared.json()
    assert cleared_body["selected_provider"] is None
    assert cleared_body["has_custom_api_key"] is False


def test_pro_user_rejects_unknown_summary_provider(client: TestClient) -> None:
    headers = _user_headers_with_plan(client, "summary-bad@example.com", "pro")
    resp = client.patch(
        "/api/v1/summary-preferences",
        json={"provider": "llamacpp"},
        headers=headers,
    )
    assert resp.status_code == 422
