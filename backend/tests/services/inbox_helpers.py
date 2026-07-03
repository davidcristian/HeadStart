"""Shared fixtures for inbox gate and orchestration service tests."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.application_log import ApplicationLog
from app.models.seen_job import SeenJob
from app.models.user import User
from app.schemas.mailbox import MailboxConfig
from tests.worker.test_pipeline import _make_search


def make_user(session: Session, email: str = "orchestrate@example.test") -> User:
    user = User(email=email, password_hash="x", is_admin=False, is_active=True, plan="pro")
    session.add(user)
    session.flush()
    return user


def mailbox_config() -> MailboxConfig:
    return MailboxConfig(
        imap_host="imap.example.com",
        imap_user="user@example.com",
        imap_password="imap-pass",
        smtp_host="smtp.example.com",
        smtp_password="smtp-pass",
        smtp_from="user@example.com",
    )


def seed_applied_job(
    session: Session, user: User, *, employer_domain: str = "company.com"
) -> SeenJob:
    search = _make_search(session, user=user)
    job = SeenJob(
        search_id=search.id,
        external_id="job-orch-1",
        hash="orch-h1",
        title="Software Engineer",
        company="Company",
        location="Remote",
        url=f"https://careers.{employer_domain}/jobs/1",
        status="applied",
        applied_at=datetime(2026, 6, 28, 12, 0, tzinfo=UTC),
    )
    session.add(job)
    session.flush()
    log = ApplicationLog(
        seen_job_id=job.id,
        status="submitted",
        dry_run=False,
        payload={"employer_domain": f"careers.{employer_domain}"},
    )
    session.add(log)
    session.flush()
    job.application_logs = [log]
    return job
