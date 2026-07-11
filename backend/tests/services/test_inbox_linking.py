"""Tests for linking inbound email to known applications."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.inbox.types import InboxMessage
from app.models.application_log import ApplicationLog
from app.models.seen_job import SeenJob
from app.services.inbox_linking import (
    email_domain,
    employer_domain_from_payload,
    link_message_to_job,
    linked_application_context,
    score_job_match,
)
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


def test_email_domain_without_at_returns_empty() -> None:
    assert email_domain("no-at-sign") == ""


def test_employer_domain_from_payload_none_and_empty() -> None:
    assert employer_domain_from_payload(None) == ""
    log = ApplicationLog(seen_job_id=1, status="submitted", dry_run=False, payload={})
    assert employer_domain_from_payload(log) == ""


def test_score_job_match_in_reply_to_not_in_outbound(db_session: Session) -> None:
    job = _seed_applied_job(db_session)
    log = job.application_logs[0]
    log.payload = {**log.payload, "outbound_message_ids": ["<other@headstart.local>"]}
    db_session.flush()
    message = InboxMessage(
        uid=8,
        from_addr="stranger@unrelated.example",
        in_reply_to="<not-matching@headstart.local>",
        subject="Re: unrelated",
        body_text="No overlap here.",
    )
    assert score_job_match(message, job, log) == 0


def test_linked_application_context_uses_payload_domain(db_session: Session) -> None:
    job = _seed_applied_job(db_session)
    log = job.application_logs[0]
    ctx = linked_application_context(job, log)
    assert ctx["employer_domain"] == "careers.acme.com"


def test_score_job_match_scores_in_reply_to_thread(db_session: Session) -> None:
    job = _seed_applied_job(db_session)
    log = job.application_logs[0]
    log.payload = {
        **log.payload,
        "outbound_message_ids": ["<apply-xyz@headstart.local>"],
    }
    db_session.flush()
    message = InboxMessage(
        uid=3,
        from_addr="stranger@unrelated.example",
        in_reply_to="<apply-xyz@headstart.local>",
        subject="Re: your note",
        body_text="Following up.",
    )
    score = score_job_match(message, job, log)
    assert score >= 80


def test_score_job_match_normalizes_in_reply_to_whitespace(db_session: Session) -> None:
    """INB-17: whitespace around Message-IDs must not drop the thread boost."""
    job = _seed_applied_job(db_session)
    log = job.application_logs[0]
    log.payload = {
        **log.payload,
        "outbound_message_ids": ["  <apply-xyz@headstart.local>  "],
    }
    db_session.flush()
    message = InboxMessage(
        uid=9,
        from_addr="stranger@unrelated.example",
        in_reply_to="  <apply-xyz@headstart.local>  ",
        subject="Re: your note",
        body_text="Following up.",
    )
    assert score_job_match(message, job, log) >= 80


def test_link_message_to_job_returns_none_below_threshold(db_session: Session) -> None:
    job = _seed_applied_job(db_session)
    message = InboxMessage(
        uid=4,
        from_addr="deals@newsletter.example",
        subject="Weekly deals",
        body_text="Big discounts today.",
    )
    assert link_message_to_job(message, [job]) is None


def test_linked_application_context_falls_back_to_url_hostname(db_session: Session) -> None:
    search = _make_search(db_session)
    job = SeenJob(
        search_id=search.id,
        external_id="job-2",
        hash="h2",
        title="Data Scientist",
        company="Globex",
        location="Remote",
        url="https://www.jobs.globex.com/posting/7",
        status="applied",
    )
    db_session.add(job)
    db_session.flush()
    log = ApplicationLog(seen_job_id=job.id, status="submitted", dry_run=False, payload={})

    ctx = linked_application_context(job, log)

    assert ctx["seen_job_id"] == job.id
    assert ctx["employer_domain"] == "jobs.globex.com"
