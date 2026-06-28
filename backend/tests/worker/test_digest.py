"""Tests for digest notification queueing and flush."""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.delivery_log import DeliveryLog
from app.models.pending_digest import PendingDigest
from app.models.search import Search
from app.notifiers.types import DeliveryResult, NotifyContext
from app.scrapers.types import JobPosting
from app.services.digest import DigestService
from app.services.pipeline import PipelineService
from tests.worker.test_pipeline import (
    FakeScraper,
    RecordingNotifier,
    _make_search,
    _pipeline,
    _posting,
)


class DigestRecordingNotifier:
    def __init__(self) -> None:
        self.batches: list[tuple[NotifyContext, list[JobPosting]]] = []

    def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
        self.batches.append((ctx, list(jobs)))
        return [DeliveryResult(external_id=j.external_id, status="sent") for j in jobs]


def _digest_search(session: Session, *, digest_interval: int = 60) -> Search:
    search = _make_search(session)
    search.notification_mode = "digest"
    search.digest_interval_seconds = digest_interval
    session.flush()
    return search


def test_pipeline_queues_jobs_in_digest_mode(db_session: Session) -> None:
    search = _digest_search(db_session)
    notifier = RecordingNotifier()

    result = _pipeline(db_session, FakeScraper([_posting("1"), _posting("2")]), notifier).run(
        search.id
    )

    assert (result.new, result.notified, result.queued) == (2, 0, 2)
    assert len(notifier.batches) == 0
    assert db_session.query(PendingDigest).count() == 2


def test_digest_flush_sends_batched_notification(db_session: Session) -> None:
    search = _digest_search(db_session, digest_interval=60)
    notifier = DigestRecordingNotifier()
    pipeline = PipelineService(
        db_session,
        scraper_factory=lambda key, http=None, rate_limiter=None: FakeScraper(
            [_posting("1"), _posting("2")]
        ),  # type: ignore[arg-type,return-value]
        notifier_factory=lambda key: notifier,  # type: ignore[arg-type,return-value]
    )
    pipeline.run(search.id)

    pending = db_session.query(PendingDigest).all()
    for row in pending:
        row.created_at = utcnow() - timedelta(seconds=120)
    db_session.flush()

    flushed = DigestService(db_session, notifier_factory=lambda key: notifier).flush_due()
    assert flushed == 1
    assert len(notifier.batches) == 1
    ctx, jobs = notifier.batches[0]
    assert ctx.digest is True
    assert ctx.search_name == search.name
    assert {j.external_id for j in jobs} == {"1", "2"}
    assert db_session.query(PendingDigest).count() == 0
    assert db_session.query(DeliveryLog).count() == 2
    db_session.refresh(search)
    assert search.last_digest_at is not None


def test_digest_flush_waits_for_interval(db_session: Session) -> None:
    search = _digest_search(db_session, digest_interval=3600)
    notifier = DigestRecordingNotifier()
    pipeline = PipelineService(
        db_session,
        scraper_factory=lambda key, http=None, rate_limiter=None: FakeScraper([_posting("1")]),  # type: ignore[arg-type,return-value]
        notifier_factory=lambda key: notifier,  # type: ignore[arg-type,return-value]
    )
    pipeline.run(search.id)

    flushed = DigestService(db_session, notifier_factory=lambda key: notifier).flush_due()
    assert flushed == 0
    assert len(notifier.batches) == 0
    assert db_session.query(PendingDigest).count() == 1


def test_digest_flush_uses_last_digest_at_as_anchor(db_session: Session) -> None:
    search = _digest_search(db_session, digest_interval=60)
    search.last_digest_at = utcnow() - timedelta(seconds=30)
    db_session.flush()

    notifier = DigestRecordingNotifier()
    PipelineService(
        db_session,
        scraper_factory=lambda key, http=None, rate_limiter=None: FakeScraper([_posting("9")]),  # type: ignore[arg-type,return-value]
        notifier_factory=lambda key: notifier,  # type: ignore[arg-type,return-value]
    ).run(search.id)

    service = DigestService(db_session, notifier_factory=lambda key: notifier)
    assert service.flush_due() == 0

    search.last_digest_at = utcnow() - timedelta(seconds=120)
    db_session.flush()
    assert service.flush_due() == 1
    assert len(notifier.batches) == 1
