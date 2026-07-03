"""Tests for apply outcome tracking metadata."""

from app.models.seen_job import SeenJob
from app.services.apply_tracking import application_tracking_payload, employer_domain_from_url


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
