"""Route tests for the application-profile endpoints."""

from fastapi.testclient import TestClient

from tests.conftest import register_and_login


def test_profile_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/profile").status_code == 401
    assert client.put("/api/v1/profile", json={}).status_code == 401
    assert client.delete("/api/v1/profile").status_code == 401


def test_profile_defaults_then_save_and_clear(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    empty = client.get("/api/v1/profile", headers=auth_headers)
    assert empty.status_code == 200
    body = empty.json()
    assert body["exists"] is False
    assert body["full_name"] == ""
    assert body["updated_at"] is None

    saved = client.put(
        "/api/v1/profile",
        json={
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "links": {"github": "https://github.com/ada"},
            "resume_text": "Pioneering programmer.",
            "answers": {"work_authorization": "UK citizen"},
        },
        headers=auth_headers,
    )
    assert saved.status_code == 200
    saved_body = saved.json()
    assert saved_body["exists"] is True
    assert saved_body["full_name"] == "Ada Lovelace"
    assert saved_body["links"]["github"] == "https://github.com/ada"
    assert saved_body["answers"] == {"work_authorization": "UK citizen"}
    assert saved_body["updated_at"] is not None

    # Persisted: a fresh GET returns the same data.
    fetched = client.get("/api/v1/profile", headers=auth_headers).json()
    assert fetched["exists"] is True
    assert fetched["resume_text"] == "Pioneering programmer."

    assert client.delete("/api/v1/profile", headers=auth_headers).status_code == 204
    assert client.get("/api/v1/profile", headers=auth_headers).json()["exists"] is False


def test_profile_is_scoped_per_user(client: TestClient) -> None:
    alice = register_and_login(client, "alice@example.com")
    bob = register_and_login(client, "bob@example.com")

    client.put("/api/v1/profile", json={"full_name": "Alice"}, headers=alice)

    assert client.get("/api/v1/profile", headers=alice).json()["full_name"] == "Alice"
    bob_profile = client.get("/api/v1/profile", headers=bob).json()
    assert bob_profile["exists"] is False
    assert bob_profile["full_name"] == ""
