"""Integration tests for the per-search pipeline and due-based scheduling."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.notification_target import NotificationTarget
from app.models.search import Search
from app.models.seen_job import SeenJob
from app.models.source import Source
from app.models.user import User
from app.notifiers.types import DeliveryResult, NotifyContext
from app.repositories.searches import SearchRepository
from app.schemas.credential import CredentialCreate
from app.scrapers.http import HttpClient
from app.scrapers.types import JobPosting, ScrapeContext
from app.services.credentials import CredentialService
from app.services.pipeline import PipelineService


class FakeScraper:
    def __init__(self, postings: list[JobPosting]) -> None:
        self.postings = postings
        self.last_ctx: ScrapeContext | None = None

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        self.last_ctx = ctx
        return self.postings


class RecordingNotifier:
    def __init__(self) -> None:
        self.batches: list[list[JobPosting]] = []

    def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
        self.batches.append(list(jobs))
        return [DeliveryResult(external_id=j.external_id, status="sent") for j in jobs]


def _make_user(session: Session, email: str = "pipe@example.test") -> User:
    user = User(email=email, password_hash="x", is_admin=True, is_active=True)
    session.add(user)
    session.flush()
    return user


def _make_search(
    session: Session,
    *,
    interval: int = 300,
    next_run_at=None,
    user: User | None = None,
) -> Search:
    owner = user or _make_user(session, email=f"pipe{utcnow().timestamp()}@example.test")
    source = Source(
        user_id=owner.id, name="src", adapter_key="greenhouse", base_url="", default_config={}
    )
    target = NotificationTarget(user_id=owner.id, name="tgt", type="ntfy", config={"topic": "x"})
    session.add_all([source, target])
    session.flush()
    search = Search(
        user_id=owner.id,
        name="search",
        source_id=source.id,
        target_id=target.id,
        query_url="",
        filters={},
        config={},
        interval_seconds=interval,
        enabled=True,
        next_run_at=next_run_at or utcnow(),
    )
    session.add(search)
    session.flush()
    return search


def _aware(dt: datetime) -> datetime:
    """Coerce to tz-aware UTC. SQLite returns naive datetimes; Postgres does not."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _posting(external_id: str, *, url: str | None = None) -> JobPosting:
    job_url = url if url is not None else f"https://acme.test/{external_id}"
    return JobPosting(
        external_id=external_id,
        title=f"Job {external_id}",
        company="ACME",
        location="Amsterdam",
        url=job_url,
    )


def _pipeline(
    session: Session, scraper: FakeScraper, notifier: RecordingNotifier
) -> PipelineService:
    return PipelineService(
        session,
        scraper_factory=lambda key, http=None: scraper,  # type: ignore[arg-type,return-value]
        notifier_factory=lambda key: notifier,  # type: ignore[arg-type,return-value]
    )


def test_pipeline_notifies_only_new_jobs(db_session: Session) -> None:
    search = _make_search(db_session)
    scraper = FakeScraper([_posting("1"), _posting("2")])
    notifier = RecordingNotifier()
    pipeline = _pipeline(db_session, scraper, notifier)

    first = pipeline.run(search.id)
    assert (first.found, first.new, first.notified, first.failed) == (2, 2, 2, 0)
    assert len(notifier.batches) == 1 and len(notifier.batches[0]) == 2

    # Second run with the same postings: nothing new, nothing sent.
    second = pipeline.run(search.id)
    assert (second.found, second.new, second.notified) == (2, 0, 0)
    assert len(notifier.batches) == 1  # notifier not called again

    # A new posting appears: only it is notified.
    scraper.postings = [_posting("1"), _posting("2"), _posting("3")]
    third = pipeline.run(search.id)
    assert (third.found, third.new, third.notified) == (3, 1, 1)
    assert [j.external_id for j in notifier.batches[1]] == ["3"]

    assert db_session.query(SeenJob).count() == 3


def test_pipeline_dedupes_within_a_single_batch(db_session: Session) -> None:
    search = _make_search(db_session)
    scraper = FakeScraper([_posting("dup"), _posting("dup")])
    notifier = RecordingNotifier()

    result = _pipeline(db_session, scraper, notifier).run(search.id)

    assert result.new == 1
    assert db_session.query(SeenJob).count() == 1


def test_pipeline_reschedules_from_now(db_session: Session) -> None:
    search = _make_search(db_session, interval=60)
    before = utcnow()
    _pipeline(db_session, FakeScraper([]), RecordingNotifier()).run(search.id)

    db_session.refresh(search)
    assert search.last_run_at is not None
    # next_run_at is roughly now + interval (in the future).
    assert _aware(search.next_run_at) > before
    assert _aware(search.next_run_at) <= utcnow() + timedelta(seconds=61)


def test_long_downtime_collapses_into_single_catchup_run(db_session: Session) -> None:
    # Search was due an hour ago (host was offline).
    overdue = utcnow() - timedelta(hours=1)
    search = _make_search(db_session, interval=60, next_run_at=overdue)

    repo = SearchRepository(db_session)
    assert search.id in [s.id for s in repo.due(utcnow())]

    _pipeline(db_session, FakeScraper([_posting("1")]), RecordingNotifier()).run(search.id)

    db_session.refresh(search)
    # After one catch-up run it is rescheduled into the future, not still overdue.
    assert _aware(search.next_run_at) > utcnow()
    assert search.id not in [s.id for s in repo.due(utcnow())]


def test_due_excludes_disabled_and_future(db_session: Session) -> None:
    repo = SearchRepository(db_session)
    due = _make_search(db_session, next_run_at=utcnow() - timedelta(seconds=5))
    future = _make_search(db_session, next_run_at=utcnow() + timedelta(hours=1))
    disabled = _make_search(db_session, next_run_at=utcnow() - timedelta(seconds=5))
    disabled.enabled = False
    db_session.flush()

    due_ids = [s.id for s in repo.due(utcnow())]
    assert due.id in due_ids
    assert future.id not in due_ids
    assert disabled.id not in due_ids


def test_pipeline_injects_owner_credentials(db_session: Session) -> None:
    search = _make_search(db_session)
    CredentialService(db_session).create(
        search.user_id,
        CredentialCreate(
            source_id=search.source_id,
            cookies={"sessionid": "abc123"},
            headers={"X-Test": "1"},
        ),
    )

    scraper = FakeScraper([_posting("1")])
    received: dict[str, object] = {}

    def factory(key: str, http: HttpClient | None = None) -> FakeScraper:
        received["http"] = http
        return scraper

    pipeline = PipelineService(
        db_session,
        scraper_factory=factory,  # type: ignore[arg-type]
        notifier_factory=lambda key: RecordingNotifier(),  # type: ignore[arg-type,return-value]
    )
    pipeline.run(search.id)

    # An HttpClient carrying the decrypted credential was built and passed in,
    # and the context also exposes the cookies/headers to the adapter.
    assert received["http"] is not None
    assert scraper.last_ctx is not None
    assert scraper.last_ctx.cookies == {"sessionid": "abc123"}
    assert scraper.last_ctx.headers == {"X-Test": "1"}


def test_pipeline_runs_without_credentials(db_session: Session) -> None:
    search = _make_search(db_session)
    scraper = FakeScraper([_posting("1")])

    def factory(key: str, http: HttpClient | None = None) -> FakeScraper:
        # No credential configured -> no HttpClient override.
        assert http is None
        return scraper

    PipelineService(
        db_session,
        scraper_factory=factory,  # type: ignore[arg-type]
        notifier_factory=lambda key: RecordingNotifier(),  # type: ignore[arg-type,return-value]
    ).run(search.id)
    assert scraper.last_ctx is not None
    assert scraper.last_ctx.cookies == {}


class FailingScraper:
    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        raise ValueError("scrape blew up")


def test_pipeline_records_last_error(db_session: Session) -> None:
    search = _make_search(db_session)
    pipeline = PipelineService(
        db_session,
        scraper_factory=lambda key, http=None: FailingScraper(),  # type: ignore[arg-type,return-value]
        notifier_factory=lambda key: RecordingNotifier(),  # type: ignore[arg-type,return-value]
    )

    result = pipeline.run(search.id)

    assert result.error == "scrape blew up"
    db_session.refresh(search)
    assert search.last_error == "scrape blew up"


def test_pipeline_clears_last_error_after_success(db_session: Session) -> None:
    search = _make_search(db_session)
    search.last_error = "old failure"
    db_session.flush()

    _pipeline(db_session, FakeScraper([]), RecordingNotifier()).run(search.id)

    db_session.refresh(search)
    assert search.last_error is None


def test_pipeline_skips_notification_for_same_url_in_another_search(
    db_session: Session,
) -> None:
    user = _make_user(db_session, email="cross@example.test")
    search_a = _make_search(db_session, user=user)
    search_b = _make_search(db_session, user=user)
    shared_url = "https://acme.test/shared-role"
    notifier = RecordingNotifier()

    first = _pipeline(
        db_session,
        FakeScraper([_posting("a-1", url=shared_url)]),
        notifier,
    ).run(search_a.id)
    assert (first.new, first.notified, first.skipped) == (1, 1, 0)

    second = _pipeline(
        db_session,
        FakeScraper([_posting("b-9", url=shared_url)]),
        notifier,
    ).run(search_b.id)
    assert (second.new, second.notified, second.skipped) == (1, 0, 1)
    assert len(notifier.batches) == 1
    assert db_session.query(SeenJob).filter_by(search_id=search_b.id).count() == 1


def test_pipeline_cross_search_dedup_is_scoped_per_user(db_session: Session) -> None:
    search_a = _make_search(db_session)
    search_b = _make_search(db_session)
    shared_url = "https://acme.test/shared-role"
    notifier = RecordingNotifier()

    _pipeline(
        db_session,
        FakeScraper([_posting("a-1", url=shared_url)]),
        notifier,
    ).run(search_a.id)
    result = _pipeline(
        db_session,
        FakeScraper([_posting("b-9", url=shared_url)]),
        notifier,
    ).run(search_b.id)

    assert (result.new, result.notified, result.skipped) == (1, 1, 0)
    assert len(notifier.batches) == 2
