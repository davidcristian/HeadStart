"""Tests for search health fields exposed via the API layer."""

from sqlalchemy.orm import Session

from app.models.delivery_log import DeliveryLog
from app.models.seen_job import SeenJob
from app.services.searches import SearchService
from tests.worker.test_pipeline import _make_search


def test_search_reads_include_recent_delivery_failures(db_session: Session) -> None:
    search = _make_search(db_session)
    job = SeenJob(
        search_id=search.id,
        external_id="job-1",
        hash="abc",
        title="Backend Engineer",
        company="ACME",
        location="Remote",
        url="https://acme.test/jobs/1",
    )
    db_session.add(job)
    db_session.flush()
    db_session.add(
        DeliveryLog(
            seen_job_id=job.id,
            target_id=search.target_id,
            status="failed",
            error="topic not found",
        )
    )
    db_session.flush()

    reads = SearchService(db_session).list_reads(search.user_id)

    assert len(reads) == 1
    assert reads[0].last_error is None
    assert len(reads[0].recent_delivery_failures) == 1
    failure = reads[0].recent_delivery_failures[0]
    assert failure.job_title == "Backend Engineer"
    assert failure.job_url == "https://acme.test/jobs/1"
    assert failure.error == "topic not found"
