"""Pipeline deduplication, filtering, and summary tests."""

from sqlalchemy.orm import Session

from app.models.seen_job import SeenJob
from app.scrapers.types import JobPosting
from tests.worker.pipeline_helpers import (
    FakeScraper,
    RecordingNotifier,
    make_search,
    make_user,
    pipeline,
    posting,
)


def test_pipeline_skips_notification_for_same_url_in_another_search(
    db_session: Session,
) -> None:
    user = make_user(db_session, email="cross@example.test")
    search_a = make_search(db_session, user=user)
    search_b = make_search(db_session, user=user)
    shared_url = "https://acme.test/shared-role"
    notifier = RecordingNotifier()

    first = pipeline(
        db_session,
        FakeScraper([posting("a-1", url=shared_url)]),
        notifier,
    ).run(search_a.id)
    assert (first.new, first.notified, first.skipped) == (1, 1, 0)

    second = pipeline(
        db_session,
        FakeScraper([posting("b-9", url=shared_url)]),
        notifier,
    ).run(search_b.id)
    assert (second.new, second.notified, second.skipped) == (1, 0, 1)
    assert len(notifier.batches) == 1
    assert db_session.query(SeenJob).filter_by(search_id=search_b.id).count() == 1


def test_pipeline_cross_search_dedup_is_scoped_per_user(db_session: Session) -> None:
    search_a = make_search(db_session)
    search_b = make_search(db_session)
    shared_url = "https://acme.test/shared-role"
    notifier = RecordingNotifier()

    pipeline(
        db_session,
        FakeScraper([posting("a-1", url=shared_url)]),
        notifier,
    ).run(search_a.id)
    result = pipeline(
        db_session,
        FakeScraper([posting("b-9", url=shared_url)]),
        notifier,
    ).run(search_b.id)

    assert (result.new, result.notified, result.skipped) == (1, 1, 0)
    assert len(notifier.batches) == 2


def test_pipeline_persists_and_notifies_match_summary(db_session: Session) -> None:
    search = make_search(db_session)
    search.filters = {"keywords": "1"}
    db_session.flush()

    scraper = FakeScraper([posting("1")])
    notifier = RecordingNotifier()
    pipeline(db_session, scraper, notifier).run(search.id)

    assert notifier.batches[0][0].summary != ""
    row = db_session.query(SeenJob).filter_by(search_id=search.id).one()
    assert row.summary == notifier.batches[0][0].summary


def test_pipeline_applies_search_filters(db_session: Session) -> None:
    search = make_search(db_session)
    search.filters = {"keywords": "engineer", "keywords_exclude": "manager"}
    db_session.flush()

    scraper = FakeScraper(
        [
            JobPosting(
                external_id="eng",
                title="Backend Engineer",
                company="ACME",
                location="Amsterdam",
                url="https://acme.test/eng",
            ),
            JobPosting(
                external_id="mgr",
                title="Engineering Manager",
                company="ACME",
                location="Amsterdam",
                url="https://acme.test/mgr",
            ),
        ]
    )
    notifier = RecordingNotifier()
    result = pipeline(db_session, scraper, notifier).run(search.id)

    assert (result.found, result.filtered, result.new, result.notified) == (2, 1, 1, 1)
    assert [job.external_id for job in notifier.batches[0]] == ["eng"]
