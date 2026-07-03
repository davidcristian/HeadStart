"""Route tests for LaTeX resume template upload."""

import io
import zipfile

from fastapi.testclient import TestClient

from tests.conftest import register_and_login

MINIMAL_TEX = rb"\documentclass{article}\begin{document}Hi\end{document}"


def _bundle_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(
            "main.tex",
            rb"\documentclass{article}\input{section}\begin{document}Hi\end{document}",
        )
        archive.writestr("section.tex", b"Section")
    return buf.getvalue()


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


def test_upload_and_delete_resume_template_bundle(client: TestClient) -> None:
    bundle = _bundle_zip()
    headers = register_and_login(client, "resume-template-bundle@example.com")
    upload = client.put(
        "/api/v1/profile/resume-template",
        headers=headers,
        files={"file": ("resume-bundle.zip", bundle, "application/zip")},
    )
    assert upload.status_code == 200
    body = upload.json()
    assert body["resume_template"]["filename"] == "resume-bundle.zip"
    assert body["resume_template"]["format"] == "bundle"
    assert body["resume_template"]["entrypoint"] == "main.tex"
    assert body["resume_template"]["file_count"] == 2
    assert body["resume_template"]["size_bytes"] == len(bundle)

    deleted = client.delete("/api/v1/profile/resume-template", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["resume_template"] is None
