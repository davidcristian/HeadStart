"""Route tests for LaTeX resume template upload."""

from fastapi.testclient import TestClient

from tests.conftest import register_and_login

MINIMAL_TEX = rb"\documentclass{article}\begin{document}Hi\end{document}"


def test_upload_resume_template_requires_auth(client: TestClient) -> None:
    resp = client.put(
        "/api/v1/profile/resume-template",
        files={"file": ("resume.tex", MINIMAL_TEX, "application/x-tex")},
    )
    assert resp.status_code == 401


def test_upload_and_delete_resume_template(client: TestClient) -> None:
    headers = register_and_login(client, "resume-template@example.com")
    upload = client.put(
        "/api/v1/profile/resume-template",
        headers=headers,
        files={"file": ("resume.tex", MINIMAL_TEX, "application/x-tex")},
    )
    assert upload.status_code == 200
    body = upload.json()
    assert body["resume_template"]["filename"] == "resume.tex"
    assert body["resume_template"]["size_bytes"] == len(MINIMAL_TEX)

    deleted = client.delete("/api/v1/profile/resume-template", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["resume_template"] is None


def test_upload_resume_template_rejects_non_tex(client: TestClient) -> None:
    headers = register_and_login(client, "resume-template-bad@example.com")
    resp = client.put(
        "/api/v1/profile/resume-template",
        headers=headers,
        files={"file": ("resume.pdf", b"%PDF", "application/pdf")},
    )
    assert resp.status_code == 400
