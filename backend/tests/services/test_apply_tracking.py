"""Tests for apply outcome tracking metadata."""

from app.models.seen_job import SeenJob
from app.schemas.profile import ResumeFile
from app.services.apply_tracking import (
    application_tracking_payload,
    application_user_consent_payload,
    employer_domain_from_url,
    merge_application_log_payload,
    scrub_adapter_payload,
)


def test_employer_domain_from_url_strips_www() -> None:
    assert employer_domain_from_url("https://www.boards.greenhouse.io/acme/jobs/1") == (
        "boards.greenhouse.io"
    )


def test_application_tracking_payload_from_seen_job() -> None:
    job = SeenJob(
        search_id=1,
        external_id="5501001",
        hash="x",
        title="Senior Engineer",
        company="ACME",
        location="Remote",
        url="https://boards.greenhouse.io/acme/jobs/5501001",
    )
    payload = application_tracking_payload(job)
    assert payload["employer_domain"] == "boards.greenhouse.io"
    assert payload["posting"]["title"] == "Senior Engineer"
    assert payload["posting"]["company"] == "ACME"
    assert payload["posting"]["external_id"] == "5501001"
    assert "user_consent" not in payload


def test_application_tracking_payload_includes_live_consent() -> None:
    job = SeenJob(
        search_id=1,
        external_id="5501001",
        hash="x",
        title="Senior Engineer",
        company="ACME",
        location="Remote",
        url="https://boards.greenhouse.io/acme/jobs/5501001",
    )
    payload = application_tracking_payload(job, live_submission=True)
    consent = payload["user_consent"]
    assert consent["basis"] == "consent"
    assert consent["mechanism"] == "source.auto_apply_enabled"
    assert consent["live_submission"] is True
    assert isinstance(consent["recorded_at"], str)


def test_application_user_consent_payload_dry_run() -> None:
    consent = application_user_consent_payload(live_submission=False)["user_consent"]
    assert consent["mechanism"] == "dry_run_preview"
    assert consent["live_submission"] is False


def test_merge_application_log_payload_preserves_prior_consent() -> None:
    job = SeenJob(
        search_id=1,
        external_id="5501001",
        hash="x",
        title="Senior Engineer",
        company="ACME",
        location="Remote",
        url="https://boards.greenhouse.io/acme/jobs/5501001",
    )
    prior = {
        "user_consent": {
            "basis": "consent",
            "mechanism": "source.auto_apply_enabled",
            "live_submission": True,
            "recorded_at": "2026-01-01T00:00:00Z",
        }
    }
    resume = ResumeFile(
        filename="cv.pdf",
        content_type="application/pdf",
        size_bytes=12,
        data=b"%PDF-fake",
    )
    merged = merge_application_log_payload(
        job,
        {"email": "ada@example.com"},
        dry_run=False,
        tailored_resume=resume,
        prior_payload=prior,
    )
    assert merged["user_consent"] == prior["user_consent"]
    assert merged["email"] == "ada@example.com"
    assert merged["tailored_resume"]["filename"] == "cv.pdf"


def test_scrub_adapter_payload_drops_credential_keys() -> None:
    """Cookies/headers/authorization (and aliases) never persist."""
    scrubbed = scrub_adapter_payload(
        {
            "email": "ada@example.com",
            "cookies": {"li_at": "secret"},
            "Cookie": "li_at=secret",
            "headers": {"Authorization": "Bearer tok"},
            "Authorization": "Bearer tok",
            "session": {"session_token": "uber-tok"},
            "sessionToken": "uber-tok",
            "nested": {
                "ok": True,
                "headers": {"X-CSRF": "x"},
                "items": [{"cookies": {"a": "1"}, "id": 7}],
            },
        }
    )
    assert scrubbed == {
        "email": "ada@example.com",
        "nested": {"ok": True, "items": [{"id": 7}]},
    }


def test_merge_application_log_payload_scrubs_adapter_secrets() -> None:
    """Merge drops credential keys before storing application_log.payload."""
    job = SeenJob(
        search_id=1,
        external_id="5501001",
        hash="x",
        title="Senior Engineer",
        company="ACME",
        location="Remote",
        url="https://boards.greenhouse.io/acme/jobs/5501001",
    )
    merged = merge_application_log_payload(
        job,
        {
            "email": "ada@example.com",
            "cookies": {"session": "abc"},
            "headers": {"Authorization": "Bearer tok"},
            "Authorization": "Bearer tok",
        },
        dry_run=True,
    )
    assert merged["email"] == "ada@example.com"
    assert "cookies" not in merged
    assert "headers" not in merged
    assert "Authorization" not in merged
    assert merged["employer_domain"] == "boards.greenhouse.io"
