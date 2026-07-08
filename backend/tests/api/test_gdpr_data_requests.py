"""Tests for GDPR data request audit logging."""

from fastapi.testclient import TestClient

from tests.conftest import register_and_login


def _delete_account(
    client: TestClient,
    *,
    password: str = "password123",
    headers: dict[str, str] | None = None,
):
    return client.request(
        "DELETE",
        "/api/v1/auth/me",
        json={"password": password},
        headers=headers,
    )


def test_export_creates_audit_log(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.get(
        "/api/v1/auth/me/export",
        headers={**auth_headers, "User-Agent": "pytest-export/1.0"},
    )
    assert resp.status_code == 200

    logs = client.get("/api/v1/admin/data-requests", headers=auth_headers).json()
    assert len(logs) == 1
    assert logs[0]["request_type"] == "export"
    assert logs[0]["user_email"] == "user@example.com"
    assert logs[0]["user_agent"] == "pytest-export/1.0"


def test_export_audit_log_ignores_untrusted_forwarded_ip(client: TestClient) -> None:
    """AUT-17: without TRUSTED_PROXY_CIDRS, forged XFF must not poison the audit IP."""
    admin = register_and_login(client, "audit-admin@example.com")
    member = register_and_login(client, "audit-member@example.com")

    resp = client.get(
        "/api/v1/auth/me/export",
        headers={
            **member,
            "X-Forwarded-For": "198.51.100.42, 10.0.0.1",
            "User-Agent": "pytest-export/2.0",
        },
    )
    assert resp.status_code == 200

    logs = client.get("/api/v1/admin/data-requests", headers=admin).json()
    assert len(logs) == 1
    assert logs[0]["ip_address"] is None
    assert logs[0]["user_agent"] == "pytest-export/2.0"


def test_delete_creates_audit_log_with_email_snapshot(client: TestClient) -> None:
    admin = register_and_login(client, "admin@example.com")
    headers = register_and_login(client, "gone@example.com")

    resp = _delete_account(
        client,
        headers={
            **headers,
            "X-Forwarded-For": "203.0.113.10",
            "User-Agent": "pytest-delete/1.0",
        },
    )
    assert resp.status_code == 204

    logs = client.get("/api/v1/admin/data-requests", headers=admin).json()
    assert len(logs) == 1
    assert logs[0]["request_type"] == "delete"
    assert logs[0]["user_id"] is None
    assert logs[0]["user_email"].startswith("erased:")
    assert "gone@example.com" not in logs[0]["user_email"]
    assert logs[0]["ip_address"] is None
    assert logs[0]["user_agent"] is None


def test_delete_redacts_prior_export_audit_rows(client: TestClient) -> None:
    admin = register_and_login(client, "admin-redact@example.com")
    member = register_and_login(client, "soon-gone@example.com")

    export = client.get(
        "/api/v1/auth/me/export",
        headers={
            **member,
            "X-Forwarded-For": "198.51.100.99",
            "User-Agent": "pytest-export-then-delete/1.0",
        },
    )
    assert export.status_code == 200

    before = client.get("/api/v1/admin/data-requests", headers=admin).json()
    assert len(before) == 1
    assert before[0]["user_email"] == "soon-gone@example.com"
    # TestClient peer is not a valid IP and XFF is untrusted by default (AUT-17).
    assert before[0]["ip_address"] is None
    assert before[0]["user_agent"] == "pytest-export-then-delete/1.0"

    assert _delete_account(client, headers=member).status_code == 204

    logs = client.get("/api/v1/admin/data-requests", headers=admin).json()
    assert len(logs) == 2
    assert {row["request_type"] for row in logs} == {"export", "delete"}
    for row in logs:
        assert row["user_email"].startswith("erased:")
        assert "soon-gone@example.com" not in row["user_email"]
        assert row["ip_address"] is None
        assert row["user_agent"] is None
        assert row["user_id"] is None


def test_failed_delete_does_not_create_audit_log(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    resp = _delete_account(client, password="wrong-password", headers=auth_headers)
    assert resp.status_code == 400
    logs = client.get("/api/v1/admin/data-requests", headers=auth_headers).json()
    assert logs == []


def test_admin_data_requests_requires_admin(client: TestClient) -> None:
    register_and_login(client, "admin@example.com")
    member = register_and_login(client, "member@example.com")

    assert client.get("/api/v1/admin/data-requests", headers=member).status_code == 403


def test_admin_lists_recent_data_requests(client: TestClient) -> None:
    admin = register_and_login(client, "admin@example.com")
    member = register_and_login(client, "member@example.com")

    client.get("/api/v1/auth/me/export", headers=member)
    client.get("/api/v1/auth/me/export", headers=member)

    logs = client.get("/api/v1/admin/data-requests", headers=admin).json()
    assert len(logs) == 2
    assert all(row["user_email"] == "member@example.com" for row in logs)
    assert logs[0]["created_at"] >= logs[1]["created_at"]
