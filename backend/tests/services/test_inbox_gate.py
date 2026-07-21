"""Tests for application-scoped inbox pre-filtering."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.email_classifiers.labels import GHOST_HEADER_TYPE, GHOST_HEADER_VALUE, GHOST_SUBJECT_PREFIX
from app.inbox.types import InboxMessage
from app.models.application_log import ApplicationLog
from app.models.seen_job import SeenJob
from app.models.user import User
from app.schemas.inbox_routing import InboxRoutingConfigUpdate
from app.schemas.mailbox import MailboxConfig, MailboxCredentialUpsert
from app.services.inbox import InboxService
from app.services.inbox_gate import (
    InboxGateContext,
    InboxGateService,
    message_references_outbound,
    sender_matches_employer_domain,
)
from app.services.inbox_routing import InboxRoutingService
from tests.worker.test_pipeline import _make_search


def _user(session: Session, email: str = "gate@example.test") -> User:
    user = User(email=email, password_hash="x", is_admin=False, is_active=True, plan="pro")
    session.add(user)
    session.flush()
    return user


def _mailbox_config() -> MailboxConfig:
    return MailboxConfig(
        imap_host="imap.example.com",
        imap_user="user@example.com",
        imap_password="imap-pass",
        smtp_host="smtp.example.com",
        smtp_password="smtp-pass",
        smtp_from="user@example.com",
    )


def _seed_applied_job(session: Session, user: User) -> SeenJob:
    search = _make_search(session, user=user)
    job = SeenJob(
        search_id=search.id,
        external_id="job-gate-1",
        hash="gate-h1",
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
            "outbound_message_ids": ["<apply-001@headstart.local>"],
            "posting": {"title": "Backend Engineer", "company": "ACME"},
        },
    )
    session.add(log)
    session.flush()
    job.application_logs = [log]
    return job


def test_sender_matches_employer_domain_accepts_subdomain() -> None:
    domains = frozenset({"careers.acme.com"})
    assert sender_matches_employer_domain("talent@careers.acme.com", domains) is True
    assert sender_matches_employer_domain("news@shopping.example", domains) is False


def test_message_references_outbound_matches_in_reply_to() -> None:
    outbound = frozenset({"<apply-001@headstart.local>"})
    message = InboxMessage(
        uid=1,
        in_reply_to="<apply-001@headstart.local>",
        subject="Re: Application",
        body_text="Follow-up question.",
    )
    assert message_references_outbound(message, outbound) is True


def test_build_context_collects_domains_and_outbound_ids(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.inbox.settings.inbox_agent_enabled", True)
    user = _user(db_session)
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=_mailbox_config()),
    )
    _seed_applied_job(db_session, user)

    ctx = InboxGateService(db_session).build_context(user.id)
    assert "careers.acme.com" in ctx.employer_domains
    assert "<apply-001@headstart.local>" in ctx.outbound_message_ids


def test_should_process_allows_employer_domain_match(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.inbox.settings.inbox_agent_enabled", True)
    user = _user(db_session, email="gate-domain@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=_mailbox_config()),
    )
    _seed_applied_job(db_session, user)
    gate = InboxGateService(db_session)
    ctx = gate.build_context(user.id)
    message = InboxMessage(
        uid=2,
        from_addr="hr@careers.acme.com",
        subject="Update",
        body_text="Quick question.",
    )
    assert gate.should_process(user.id, message, ctx) is True


def test_should_process_ignores_unrelated_sender(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.inbox.settings.inbox_agent_enabled", True)
    user = _user(db_session, email="gate-ignore@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=_mailbox_config()),
    )
    _seed_applied_job(db_session, user)
    gate = InboxGateService(db_session)
    ctx = gate.build_context(user.id)
    message = InboxMessage(
        uid=3,
        from_addr="deals@newsletter.example",
        subject="Weekly deals",
        body_text="50% off shoes.",
    )
    assert gate.should_process(user.id, message, ctx) is False


def test_should_process_allows_self_ghost_archive_without_applications(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr("app.services.inbox.settings.inbox_agent_enabled", True)
    user = _user(db_session, email="gate-ghost@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=_mailbox_config()),
    )
    gate = InboxGateService(db_session)
    ctx = InboxGateContext(
        employer_domains=frozenset(),
        outbound_message_ids=frozenset(),
        sender_allowlist=frozenset(),
    )
    message = InboxMessage(
        uid=4,
        from_addr="user@example.com",
        to_addrs=["user@example.com"],
        subject=f"{GHOST_SUBJECT_PREFIX} No reply: Engineer at ACME",
        body_text="Ghost summary.",
        raw_headers={GHOST_HEADER_TYPE: GHOST_HEADER_VALUE},
    )
    assert gate.should_process(user.id, message, ctx) is True


def test_should_process_allows_sender_allowlist(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.inbox.settings.inbox_agent_enabled", True)
    user = _user(db_session, email="gate-allowlist@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=_mailbox_config()),
    )
    InboxRoutingService(db_session).update_config(
        user.id,
        InboxRoutingConfigUpdate(sender_allowlist=["trusted.recruiter@partner.example"]),
    )
    gate = InboxGateService(db_session)
    ctx = gate.build_context(user.id)
    message = InboxMessage(
        uid=5,
        from_addr="trusted.recruiter@partner.example",
        subject="Heads up",
        body_text="Are you still looking?",
    )
    assert gate.should_process(user.id, message, ctx) is True


def test_gate_excludes_archived_applications(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.inbox.settings.inbox_agent_enabled", True)
    user = _user(db_session, email="gate-archived@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=_mailbox_config()),
    )
    job = _seed_applied_job(db_session, user)
    job.status = "archived"
    db_session.flush()

    ctx = InboxGateService(db_session).build_context(user.id)
    assert ctx.employer_domains == frozenset()


def test_should_process_allows_outbound_reference_match(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.inbox.settings.inbox_agent_enabled", True)
    user = _user(db_session, email="gate-ref@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=_mailbox_config()),
    )
    _seed_applied_job(db_session, user)
    gate = InboxGateService(db_session)
    ctx = gate.build_context(user.id)
    message = InboxMessage(
        uid=6,
        from_addr="unknown@third-party.example",
        in_reply_to="<apply-001@headstart.local>",
        subject="Re: your application",
        body_text="Thanks.",
    )
    assert gate.should_process(user.id, message, ctx) is True


def test_build_context_falls_back_to_job_url_domain(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.inbox.settings.inbox_agent_enabled", True)
    user = _user(db_session, email="gate-urlfallback@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=_mailbox_config()),
    )
    search = _make_search(db_session, user=user)
    job = SeenJob(
        search_id=search.id,
        external_id="job-url",
        hash="url-h1",
        title="Backend Engineer",
        company="ACME",
        location="Remote",
        url="https://www.jobs.acme.com/jobs/9",
        status="applied",
        applied_at=datetime(2026, 6, 28, 12, 0, tzinfo=UTC),
    )
    db_session.add(job)
    db_session.flush()
    log = ApplicationLog(seen_job_id=job.id, status="submitted", dry_run=False, payload={})
    db_session.add(log)
    db_session.flush()
    job.application_logs = [log]

    ctx = InboxGateService(db_session).build_context(user.id)
    assert "jobs.acme.com" in ctx.employer_domains


def test_build_context_skips_job_without_domain(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.inbox.settings.inbox_agent_enabled", True)
    user = _user(db_session, email="gate-nodomain@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=_mailbox_config()),
    )
    search = _make_search(db_session, user=user)
    job = SeenJob(
        search_id=search.id,
        external_id="job-nodomain",
        hash="nd-h1",
        title="Backend Engineer",
        company="ACME",
        location="Remote",
        url="not-a-valid-url",
        status="applied",
        applied_at=datetime(2026, 6, 28, 12, 0, tzinfo=UTC),
    )
    db_session.add(job)
    db_session.flush()
    log = ApplicationLog(seen_job_id=job.id, status="submitted", dry_run=False, payload={})
    db_session.add(log)
    db_session.flush()
    job.application_logs = [log]

    ctx = InboxGateService(db_session).build_context(user.id)
    assert ctx.employer_domains == frozenset()


def test_sender_allowlist_empty_when_no_credential(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.inbox.settings.inbox_agent_enabled", True)
    user = _user(db_session, email="gate-nocred@example.test")
    gate = InboxGateService(db_session)
    assert gate._sender_allowlist(user.id) == set()
