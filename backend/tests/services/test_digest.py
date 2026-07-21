"""Service-level tests for digest queueing and flush branches."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.delivery_log import DeliveryLog
from app.models.pending_digest import PendingDigest
from app.notifiers.types import DeliveryResult, NotifyContext
from app.scrapers.types import JobPosting
from app.services.digest import DigestService
from app.services.pipeline import PipelineService
from tests.worker.pipeline_helpers import FakeScraper, make_search, posting


class RecordingDigestNotifier:
    def __init__(self) -> None:
        self.batches: list[tuple[NotifyContext, list[JobPosting]]] = []

    def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
        self.batches.append((ctx, list(jobs)))
        return [DeliveryResult(external_id=j.external_id, status="sent") for j in jobs]


def _digest_search(session: Session, *, interval: int = 60):
    search = make_search(session)
    search.notification_mode = "digest"
    search.digest_interval_seconds = interval
    session.flush()
    return search


def _seed_pending(session: Session, notifier, search, ids: list[str]) -> None:
    PipelineService(
        session,
        scraper_factory=lambda key, http=None, rate_limiter=None: FakeScraper(
            [posting(i) for i in ids]
        ),  # type: ignore[arg-type,return-value]
        notifier_factory=lambda key: notifier,  # type: ignore[arg-type,return-value]
    ).run(search.id)


def test_queue_counts_enqueued(db_session: Session) -> None:
    search = _digest_search(db_session)
    queued = DigestService(db_session).queue(search.id, [])
    assert queued == 0


def test_queue_batches_seen_job_ids(db_session: Session) -> None:
    """DigestService.queue persists all ids via one repository batch."""
    search = _digest_search(db_session)
    from app.models.seen_job import SeenJob

    jobs = []
    for eid in ("q1", "q2", "q3"):
        job = SeenJob(
            search_id=search.id,
            external_id=eid,
            hash=f"hash-{eid}",
            title=f"Job {eid}",
            company="Acme",
            location="Remote",
            url=f"https://example.test/{eid}",
            status="new",
        )
        db_session.add(job)
        jobs.append(job)
    db_session.flush()

    queued = DigestService(db_session).queue(search.id, [j.id for j in jobs])
    assert queued == 3
    assert db_session.query(PendingDigest).count() == 3


def test_flush_due_sends_when_interval_elapsed(db_session: Session) -> None:
    search = _digest_search(db_session, interval=60)
    notifier = RecordingDigestNotifier()
    _seed_pending(db_session, notifier, search, ["1", "2"])
    old = (utcnow() - timedelta(seconds=120)).replace(tzinfo=None)
    for row in db_session.query(PendingDigest).all():
        row.created_at = old
    db_session.flush()

    flushed = DigestService(db_session, notifier_factory=lambda key: notifier).flush_due()
    assert flushed == 1
    assert len(notifier.batches) == 1
    assert db_session.query(PendingDigest).count() == 0
    assert db_session.query(DeliveryLog).count() == 2


def test_flush_due_waits_when_not_elapsed(db_session: Session) -> None:
    search = _digest_search(db_session, interval=3600)
    notifier = RecordingDigestNotifier()
    _seed_pending(db_session, notifier, search, ["1"])

    flushed = DigestService(db_session, notifier_factory=lambda key: notifier).flush_due()
    assert flushed == 0
    assert db_session.query(PendingDigest).count() == 1


def test_flush_due_uses_last_digest_anchor(db_session: Session) -> None:
    search = _digest_search(db_session, interval=60)
    notifier = RecordingDigestNotifier()
    _seed_pending(db_session, notifier, search, ["9"])

    service = DigestService(db_session, notifier_factory=lambda key: notifier)
    search.last_digest_at = utcnow() - timedelta(seconds=30)
    db_session.flush()
    assert service.flush_due() == 0

    search.last_digest_at = utcnow() - timedelta(seconds=120)
    db_session.flush()
    assert service.flush_due() == 1


def test_flush_due_skips_search_locked_by_another_tick(db_session: Session) -> None:
    from unittest.mock import patch

    search = _digest_search(db_session, interval=60)
    notifier = RecordingDigestNotifier()
    _seed_pending(db_session, notifier, search, ["1"])

    service = DigestService(db_session, notifier_factory=lambda key: notifier)
    # Simulate another beat tick holding the row lock: get_for_update returns None.
    with patch.object(service.searches, "get_for_update", return_value=None):
        flushed = service.flush_due()

    assert flushed == 0
    assert notifier.batches == []
    assert db_session.query(PendingDigest).count() == 1


def test_flush_search_returns_early_when_no_target(db_session: Session) -> None:
    search = _digest_search(db_session, interval=60)
    notifier = RecordingDigestNotifier()
    _seed_pending(db_session, notifier, search, ["1"])
    # Remove the target link so _flush_search bails without notifying.
    search.target_id = None
    search.target = None
    db_session.flush()

    pending = DigestService(db_session).pending.list_for_search(search.id)
    DigestService(db_session, notifier_factory=lambda key: notifier)._flush_search(search, pending)
    assert notifier.batches == []
    # Nothing was deleted since flush returned early.
    assert db_session.query(PendingDigest).count() == 1


def test_flush_search_records_error_and_reraises(db_session: Session) -> None:
    search = _digest_search(db_session, interval=60)

    class ExplodingNotifier:
        def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
            raise RuntimeError("digest boom")

    exploding = ExplodingNotifier()
    _seed_pending(db_session, RecordingDigestNotifier(), search, ["1"])
    pending = DigestService(db_session).pending.list_for_search(search.id)

    service = DigestService(db_session, notifier_factory=lambda key: exploding)
    with pytest.raises(RuntimeError, match="digest boom"):
        service._flush_search(search, pending)


def test_flush_due_isolates_per_search_notifier_failure(db_session: Session) -> None:
    """One bad target must not block other due digests."""
    # Lower id flushes first and fails; higher id must still succeed.
    failing = _digest_search(db_session, interval=60)
    failing.name = "failing"
    succeeding = _digest_search(db_session, interval=60)
    succeeding.name = "succeeding"
    db_session.flush()
    assert failing.id < succeeding.id

    class SelectiveNotifier:
        def __init__(self) -> None:
            self.sent: list[str] = []

        def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
            if ctx.search_name == "failing":
                raise RuntimeError("bad webhook")
            self.sent.append(ctx.search_name or "")
            return [DeliveryResult(external_id=j.external_id, status="sent") for j in jobs]

    notifier = SelectiveNotifier()
    _seed_pending(db_session, RecordingDigestNotifier(), failing, ["f1"])
    _seed_pending(db_session, RecordingDigestNotifier(), succeeding, ["s1"])
    old = (utcnow() - timedelta(seconds=120)).replace(tzinfo=None)
    for row in db_session.query(PendingDigest).all():
        row.created_at = old
    # Commit setup so a failed flush's rollback cannot undo the due window.
    db_session.commit()

    flushed = DigestService(db_session, notifier_factory=lambda key: notifier).flush_due()
    assert flushed == 1
    assert notifier.sent == ["succeeding"]
    db_session.expire_all()
    assert db_session.query(PendingDigest).filter_by(search_id=failing.id).count() == 1
    assert db_session.query(PendingDigest).filter_by(search_id=succeeding.id).count() == 0
    assert db_session.query(DeliveryLog).count() == 1


def test_flush_due_commits_before_later_search_failure(db_session: Session) -> None:
    """A later send failure must not roll back an earlier delivered digest."""
    first = _digest_search(db_session, interval=60)
    first.name = "first"
    second = _digest_search(db_session, interval=60)
    second.name = "second"
    db_session.flush()
    assert first.id < second.id

    class FailSecondNotifier:
        def __init__(self) -> None:
            self.calls = 0

        def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
            self.calls += 1
            if ctx.search_name == "second":
                raise RuntimeError("second boom")
            return [DeliveryResult(external_id=j.external_id, status="sent") for j in jobs]

    notifier = FailSecondNotifier()
    _seed_pending(db_session, RecordingDigestNotifier(), first, ["a"])
    _seed_pending(db_session, RecordingDigestNotifier(), second, ["b"])
    old = (utcnow() - timedelta(seconds=120)).replace(tzinfo=None)
    for row in db_session.query(PendingDigest).all():
        row.created_at = old
    db_session.commit()

    flushed = DigestService(db_session, notifier_factory=lambda key: notifier).flush_due()
    assert flushed == 1
    assert notifier.calls == 2

    db_session.expire_all()
    assert db_session.query(PendingDigest).filter_by(search_id=first.id).count() == 0
    assert db_session.query(PendingDigest).filter_by(search_id=second.id).count() == 1
    refreshed = db_session.get(type(first), first.id)
    assert refreshed is not None
    assert refreshed.last_digest_at is not None
    assert db_session.query(DeliveryLog).count() == 1


def test_flush_ignores_unknown_external_ids(db_session: Session) -> None:
    search = _digest_search(db_session, interval=60)

    class ExtraNotifier:
        def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
            return [
                *[DeliveryResult(external_id=j.external_id, status="sent") for j in jobs],
                DeliveryResult(external_id="stranger", status="sent"),
            ]

    notifier = ExtraNotifier()
    _seed_pending(db_session, RecordingDigestNotifier(), search, ["1"])
    old = (utcnow() - timedelta(seconds=120)).replace(tzinfo=None)
    for row in db_session.query(PendingDigest).all():
        row.created_at = old
    db_session.flush()

    flushed = DigestService(db_session, notifier_factory=lambda key: notifier).flush_due()
    assert flushed == 1
    # Only the known job produced a delivery log; the stranger id is ignored.
    assert db_session.query(DeliveryLog).count() == 1


def test_flush_due_skips_send_when_notifier_not_on_plan(db_session: Session) -> None:
    search = _digest_search(db_session, interval=60)
    search.target.type = "webhook"
    search.target.config = {"url": "https://example.test/hook"}
    db_session.flush()

    notifier = RecordingDigestNotifier()
    _seed_pending(db_session, RecordingDigestNotifier(), search, ["1"])
    old = (utcnow() - timedelta(seconds=120)).replace(tzinfo=None)
    for row in db_session.query(PendingDigest).all():
        row.created_at = old
    search.user.is_admin = False
    search.user.plan = "free"
    db_session.flush()

    flushed = DigestService(db_session, notifier_factory=lambda key: notifier).flush_due()
    assert flushed == 1
    assert len(notifier.batches) == 0
    assert db_session.query(PendingDigest).count() == 0
    assert db_session.query(DeliveryLog).count() == 0
    assert search.last_digest_at is not None
