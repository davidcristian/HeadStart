"""Cheap pre-filter: only classify mail plausibly tied to active applications."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.inbox.ghost_message import is_self_ghost_archive_message
from app.inbox.routing import merge_routing_config
from app.inbox.types import InboxMessage
from app.models.application_log import ApplicationLog
from app.models.seen_job import SeenJob
from app.repositories.applications import ApplicationPipelineRepository
from app.repositories.mailbox_credentials import MailboxCredentialRepository
from app.schemas.application_pipeline import ApplicationPipelineStage
from app.services.applications import derive_pipeline_stage, latest_live_attempt
from app.services.inbox import InboxService
from app.services.inbox_linking import email_domain, employer_domain_from_payload

GATE_ELIGIBLE_STAGES: frozenset[ApplicationPipelineStage] = frozenset(
    {"awaiting_reply", "interview_pending", "ghosted"}
)


@dataclass(frozen=True)
class InboxGateContext:
    """Precomputed matching data for one user's gate-eligible applications."""

    employer_domains: frozenset[str]
    outbound_message_ids: frozenset[str]
    sender_allowlist: frozenset[str]


class InboxGateService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.pipeline = ApplicationPipelineRepository(session)
        self.credentials = MailboxCredentialRepository(session)
        self.inbox = InboxService(session)

    def build_context(self, user_id: int) -> InboxGateContext:
        """Collect employer domains and thread ids from active/ghosted applications."""
        jobs = self._gate_eligible_jobs(user_id)
        employer_domains: set[str] = set()
        outbound_ids: set[str] = set()
        for job in jobs:
            log = latest_live_attempt(job.application_logs)
            domain = employer_domain_from_payload(log)
            if not domain:
                domain = email_domain_from_job_url(job)
            if domain:
                employer_domains.add(domain)
            outbound_ids.update(outbound_message_ids_from_log(log))
        allowlist = self._sender_allowlist(user_id)
        return InboxGateContext(
            employer_domains=frozenset(employer_domains),
            outbound_message_ids=frozenset(outbound_ids),
            sender_allowlist=frozenset(allowlist),
        )

    def should_process(self, user_id: int, message: InboxMessage, ctx: InboxGateContext) -> bool:
        """Return True when a message should enter classification."""
        mailbox_email = self._mailbox_user_email(user_id)
        if is_self_ghost_archive_message(message, mailbox_email):
            return True
        if sender_on_allowlist(message.from_addr, ctx.sender_allowlist):
            return True
        if message_references_outbound(message, ctx.outbound_message_ids):
            return True
        return sender_matches_employer_domain(message.from_addr, ctx.employer_domains)

    def _gate_eligible_jobs(self, user_id: int) -> list[SeenJob]:
        jobs = self.pipeline.list_jobs_for_user(user_id, limit=200)
        eligible: list[SeenJob] = []
        for job in jobs:
            stage = derive_pipeline_stage(job, latest_live_attempt(job.application_logs))
            if stage in GATE_ELIGIBLE_STAGES:
                eligible.append(job)
        return eligible

    def _sender_allowlist(self, user_id: int) -> set[str]:
        credential = self.credentials.get_for_user(user_id)
        if credential is None:
            return set()
        config = merge_routing_config(credential.routing_config)
        return {addr.strip().lower() for addr in config.sender_allowlist if addr.strip()}

    def _mailbox_user_email(self, user_id: int) -> str:
        credential = self.inbox.get_read_optional(user_id)
        if credential is not None and credential.imap_user:
            return credential.imap_user
        return ""


def email_domain_from_job_url(job: SeenJob) -> str:
    """Fallback employer domain from the job posting URL hostname."""
    from urllib.parse import urlparse

    host = urlparse(job.url).hostname or ""
    return host.lower().removeprefix("www.")


def outbound_message_ids_from_log(log: ApplicationLog | None) -> set[str]:
    """Collect stored outbound Message-IDs from an application log payload."""
    if log is None or not log.payload:
        return set()
    raw = log.payload.get("outbound_message_ids") or []
    if not isinstance(raw, list):
        return set()
    return {normalize_message_id(str(item)) for item in raw if str(item).strip()}


def normalize_message_id(value: str) -> str:
    """Normalize a Message-ID for comparison."""
    return value.strip()


def parse_referenced_message_ids(value: str) -> list[str]:
    """Parse Message-ID tokens from In-Reply-To / References headers."""
    tokens = re.findall(r"<[^>]+>", value)
    if tokens:
        return [normalize_message_id(token) for token in tokens]
    return [normalize_message_id(part) for part in value.split() if part.strip()]


def message_references_outbound(message: InboxMessage, outbound_ids: frozenset[str]) -> bool:
    """Return True when inbound headers reference a known outbound application email."""
    if not outbound_ids:
        return False
    if message.in_reply_to and normalize_message_id(message.in_reply_to) in outbound_ids:
        return True
    if message.references:
        for ref in parse_referenced_message_ids(message.references):
            if ref in outbound_ids:
                return True
    return False


def sender_on_allowlist(from_addr: str, allowlist: frozenset[str]) -> bool:
    """Return True when the sender is on the optional allowlist."""
    if not allowlist:
        return False
    return from_addr.strip().lower() in allowlist


def sender_matches_employer_domain(from_addr: str, employer_domains: frozenset[str]) -> bool:
    """Return True when the sender domain matches a gate-eligible employer domain."""
    sender_domain = email_domain(from_addr)
    if not sender_domain or not employer_domains:
        return False
    for domain in employer_domains:
        if sender_domain == domain or sender_domain.endswith(f".{domain}"):
            return True
    return False
