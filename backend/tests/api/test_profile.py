"""Route tests for the application-profile endpoints."""

from fastapi.testclient import TestClient

from tests.conftest import register_and_login


def test_profile_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/profile").status_code == 401
    assert client.put("/api/v1/profile", json={}).status_code == 401
    assert client.delete("/api/v1/profile").status_code == 401
    resume_upload = client.put(
        "/api/v1/profile/resume",
        files={"file": ("r.pdf", b"%PDF", "application/pdf")},
    )
    assert resume_upload.status_code == 401
    assert client.delete("/api/v1/profile/resume").status_code == 401


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


def test_resume_upload_replace_and_delete(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.put(
        "/api/v1/profile",
        json={"full_name": "Ada Lovelace", "email": "ada@example.com"},
        headers=auth_headers,
    )

    uploaded = client.put(
        "/api/v1/profile/resume",
        headers=auth_headers,
        files={"file": ("resume.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert uploaded.status_code == 200
    body = uploaded.json()
    assert body["resume_file"]["filename"] == "resume.pdf"
    assert body["resume_file"]["content_type"] == "application/pdf"
    assert body["resume_file"]["size_bytes"] == len(b"%PDF-1.4 test")
    assert body["full_name"] == "Ada Lovelace"

    fetched = client.get("/api/v1/profile", headers=auth_headers).json()
    assert fetched["resume_file"]["filename"] == "resume.pdf"
    assert "data" not in fetched["resume_file"]

    replaced = client.put(
        "/api/v1/profile/resume",
        headers=auth_headers,
        files={
            "file": (
                "cv.docx",
                b"docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert replaced.status_code == 200
    assert replaced.json()["resume_file"]["filename"] == "cv.docx"

    cleared = client.delete("/api/v1/profile/resume", headers=auth_headers)
    assert cleared.status_code == 200
    assert cleared.json()["resume_file"] is None
    assert cleared.json()["full_name"] == "Ada Lovelace"


def test_resume_upload_rejects_invalid_type(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    resp = client.put(
        "/api/v1/profile/resume",
        headers=auth_headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


def test_resume_upload_rejects_oversized_file(
    client: TestClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr("app.api.v1.profile.settings.profile_resume_max_bytes", 1024)
    resp = client.put(
        "/api/v1/profile/resume",
        headers=auth_headers,
        files={"file": ("resume.pdf", b"x" * 1025, "application/pdf")},
    )
    assert resp.status_code == 400
    assert "exceeds" in resp.json()["detail"].lower()
