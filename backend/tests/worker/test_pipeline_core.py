"""Core pipeline integration tests."""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.seen_job import SeenJob
from app.repositories.searches import SearchRepository
from app.schemas.credential import CredentialCreate
from app.scrapers.http import HttpClient
from app.services.credentials import CredentialService
from app.services.pipeline import PipelineService
from tests.worker.pipeline_helpers import (
    FailingScraper,
    FakeScraper,
    RecordingNotifier,
    aware,
    make_search,
    pipeline,
    posting,
)


def test_pipeline_notifies_only_new_jobs(db_session: Session) -> None:
    search = make_search(db_session)
    scraper = FakeScraper([posting("1"), posting("2")])
    notifier = RecordingNotifier()
    svc = pipeline(db_session, scraper, notifier)

    first = svc.run(search.id)
    assert (first.found, first.new, first.notified, first.failed) == (2, 2, 2, 0)
    assert len(notifier.batches) == 1 and len(notifier.batches[0]) == 2

    second = svc.run(search.id)
    assert (second.found, second.new, second.notified) == (2, 0, 0)
    assert len(notifier.batches) == 1

    scraper.postings = [posting("1"), posting("2"), posting("3")]
    third = svc.run(search.id)
    assert (third.found, third.new, third.notified) == (3, 1, 1)
    assert [j.external_id for j in notifier.batches[1]] == ["3"]

    assert db_session.query(SeenJob).count() == 3


def test_pipeline_dedupes_within_a_single_batch(db_session: Session) -> None:
    search = make_search(db_session)
    scraper = FakeScraper([posting("dup"), posting("dup")])
    notifier = RecordingNotifier()

    result = pipeline(db_session, scraper, notifier).run(search.id)

    assert result.new == 1
    assert db_session.query(SeenJob).count() == 1


def test_pipeline_reschedules_from_now(db_session: Session) -> None:
    search = make_search(db_session, interval=60)
    before = utcnow()
    pipeline(db_session, FakeScraper([]), RecordingNotifier()).run(search.id)

    db_session.refresh(search)
    assert search.last_run_at is not None
    assert aware(search.next_run_at) > before
    assert aware(search.next_run_at) <= utcnow() + timedelta(seconds=61)


def test_long_downtime_collapses_into_single_catchup_run(db_session: Session) -> None:
    overdue = utcnow() - timedelta(hours=1)
    search = make_search(db_session, interval=60, next_run_at=overdue)

    repo = SearchRepository(db_session)
    assert search.id in [s.id for s in repo.due(utcnow())]

    pipeline(db_session, FakeScraper([posting("1")]), RecordingNotifier()).run(search.id)

    db_session.refresh(search)
    assert aware(search.next_run_at) > utcnow()
    assert search.id not in [s.id for s in repo.due(utcnow())]


def test_due_excludes_disabled_and_future(db_session: Session) -> None:
    repo = SearchRepository(db_session)
    due = make_search(db_session, next_run_at=utcnow() - timedelta(seconds=5))
    future = make_search(db_session, next_run_at=utcnow() + timedelta(hours=1))
    disabled = make_search(db_session, next_run_at=utcnow() - timedelta(seconds=5))
    disabled.enabled = False
    db_session.flush()

    due_ids = [s.id for s in repo.due(utcnow())]
    assert due.id in due_ids
    assert future.id not in due_ids
    assert disabled.id not in due_ids


def test_pipeline_injects_owner_credentials(db_session: Session) -> None:
    search = make_search(db_session)
    CredentialService(db_session).create(
        search.user_id,
        CredentialCreate(
            source_id=search.source_id,
            cookies={"sessionid": "abc123"},
            headers={"X-Test": "1"},
        ),
    )

    scraper = FakeScraper([posting("1")])
    received: dict[str, object] = {}

    def factory(key: str, http: HttpClient | None = None, rate_limiter=None) -> FakeScraper:
        received["http"] = http
        return scraper

    PipelineService(
        db_session,
        scraper_factory=factory,  # type: ignore[arg-type]
        notifier_factory=lambda key: RecordingNotifier(),  # type: ignore[arg-type,return-value]
    ).run(search.id)

    assert received["http"] is not None
    assert scraper.last_ctx is not None
    assert scraper.last_ctx.cookies == {"sessionid": "abc123"}
    assert scraper.last_ctx.headers == {"X-Test": "1"}


def test_pipeline_runs_without_credentials(db_session: Session) -> None:
    search = make_search(db_session)
    scraper = FakeScraper([posting("1")])

    def factory(key: str, http: HttpClient | None = None, rate_limiter=None) -> FakeScraper:
        assert http is not None
        assert rate_limiter is not None
        return scraper

    PipelineService(
        db_session,
        scraper_factory=factory,  # type: ignore[arg-type]
        notifier_factory=lambda key: RecordingNotifier(),  # type: ignore[arg-type,return-value]
    ).run(search.id)
    assert scraper.last_ctx is not None
    assert scraper.last_ctx.cookies == {}


def test_pipeline_records_last_error(db_session: Session) -> None:
    search = make_search(db_session)
    svc = PipelineService(
        db_session,
        scraper_factory=lambda key, http=None, rate_limiter=None: FailingScraper(),  # type: ignore[arg-type,return-value]
        notifier_factory=lambda key: RecordingNotifier(),  # type: ignore[arg-type,return-value]
    )

    result = svc.run(search.id)

    assert result.error == "scrape blew up"
    db_session.refresh(search)
    assert search.last_error == "scrape blew up"


def test_pipeline_clears_last_error_after_success(db_session: Session) -> None:
    search = make_search(db_session)
    search.last_error = "old failure"
    db_session.flush()

    pipeline(db_session, FakeScraper([]), RecordingNotifier()).run(search.id)

    db_session.refresh(search)
    assert search.last_error is None
