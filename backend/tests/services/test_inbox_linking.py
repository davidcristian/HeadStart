"""Tests for linking inbound email to known applications."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.inbox.types import InboxMessage
from app.models.application_log import ApplicationLog
from app.models.seen_job import SeenJob
from app.services.inbox_linking import link_message_to_job, score_job_match
from tests.worker.test_pipeline import _make_search


def _seed_applied_job(session: Session) -> SeenJob:
    search = _make_search(session)
    job = SeenJob(
        search_id=search.id,
        external_id="job-1",
        hash="h1",
        title="Backend Engineer",
        company="ACME",
        location="Remote",
        url="https://careers.acme.com/jobs/1",
        status="applied",
        applied_at=datetime(2026, 6, 28, 12, 0, tzinfo=UTC),
    )
    session.add(job)
    session.flush()
    log = ApplicationLog(
        seen_job_id=job.id,
        status="submitted",
        dry_run=False,
        payload={
            "employer_domain": "careers.acme.com",
            "posting": {"title": "Backend Engineer", "company": "ACME"},
        },
    )
    session.add(log)
    session.flush()
    job.application_logs = [log]
    return job


def test_score_job_match_prefers_employer_domain(db_session: Session) -> None:
    job = _seed_applied_job(db_session)
    message = InboxMessage(
        uid=1,
        from_addr="talent@careers.acme.com",
        subject="ACME Backend Engineer follow-up",
        body_text="Quick question about your availability.",
    )
    score = score_job_match(message, job, job.application_logs[0])
    assert score >= 50


def test_link_message_to_job_matches_domain_and_title(db_session: Session) -> None:
    job = _seed_applied_job(db_session)
    message = InboxMessage(
        uid=2,
        from_addr="hr@careers.acme.com",
        subject="Re: Backend Engineer",
        body_text="Can you share your work authorization status?",
    )
    linked = link_message_to_job(message, [job])
    assert linked is not None
    assert linked.id == job.id
