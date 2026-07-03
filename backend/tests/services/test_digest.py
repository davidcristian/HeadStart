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
