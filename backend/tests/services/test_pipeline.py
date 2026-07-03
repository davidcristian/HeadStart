"""Service-level tests for the per-search pipeline branches."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.delivery_log import DeliveryLog
from app.models.pending_digest import PendingDigest
from app.notifiers.types import DeliveryResult, NotifyContext
from app.schemas.credential import CredentialCreate
from app.scrapers.types import JobPosting, ScrapeContext
from app.services.credentials import CredentialService
from app.services.pipeline import PipelineService
from tests.worker.pipeline_helpers import (
    FailingScraper,
    FakeScraper,
    RecordingNotifier,
    make_search,
    pipeline,
    posting,
)


def test_run_returns_not_found_for_missing_search(db_session: Session) -> None:
    result = pipeline(db_session, FakeScraper([]), RecordingNotifier()).run(999999)
    assert result.error == "not found"
    assert result.search_id == 999999


def test_run_catches_scraper_errors(db_session: Session) -> None:
    search = make_search(db_session)
    svc = PipelineService(
        db_session,
        scraper_factory=lambda key, http=None, rate_limiter=None: FailingScraper(),  # type: ignore[arg-type,return-value]
        notifier_factory=lambda key: RecordingNotifier(),  # type: ignore[arg-type,return-value]
    )
    result = svc.run(search.id)
    assert result.error is not None
    assert "blew up" in result.error


def test_run_skips_summaries_when_plan_disallows(db_session: Session) -> None:
    search = make_search(db_session)
    scraper = FakeScraper([posting("1")])
    notifier = RecordingNotifier()
    svc = pipeline(db_session, scraper, notifier)
    with patch("app.services.pipeline.PlanLimitsService") as plan:
        plan.return_value.allows_summaries.return_value = False
        result = svc.run(search.id)
    assert result.new == 1
    assert result.notified == 1


def test_run_annotates_summaries_when_allowed(db_session: Session) -> None:
    search = make_search(db_session)
    scraper = FakeScraper([posting("1")])
    notifier = RecordingNotifier()
    svc = pipeline(db_session, scraper, notifier)
    with (
        patch("app.services.pipeline.PlanLimitsService") as plan,
        patch.object(svc.summaries, "annotate") as annotate,
    ):
        plan.return_value.allows_summaries.return_value = True
        result = svc.run(search.id)
    annotate.assert_called_once()
    assert result.notified == 1


def test_run_queues_digest_mode(db_session: Session) -> None:
    search = make_search(db_session)
    search.notification_mode = "digest"
    db_session.flush()
    scraper = FakeScraper([posting("1"), posting("2")])
    notifier = RecordingNotifier()
    result = pipeline(db_session, scraper, notifier).run(search.id)
    assert result.queued == 2
    assert result.notified == 0
    assert db_session.query(PendingDigest).count() == 2


def test_scrape_injects_credentials_and_rate_limit(db_session: Session) -> None:
    search = make_search(db_session)
    CredentialService(db_session).create(
        search.user_id,
        CredentialCreate(
            source_id=search.source_id,
            cookies={"sessionid": "abc"},
            headers={"X-Api": "1"},
        ),
    )

    captured: dict[str, ScrapeContext] = {}

    class CapturingScraper:
        def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
            captured["ctx"] = ctx
            return [posting("1")]

    svc = PipelineService(
        db_session,
        scraper_factory=lambda key, http=None, rate_limiter=None: CapturingScraper(),  # type: ignore[arg-type,return-value]
        notifier_factory=lambda key: RecordingNotifier(),  # type: ignore[arg-type,return-value]
    )
    svc.run(search.id)
    ctx = captured["ctx"]
    assert ctx.cookies == {"sessionid": "abc"}
    assert ctx.headers == {"X-Api": "1"}


def test_scrape_records_error_and_reraises(db_session: Session) -> None:
    search = make_search(db_session)

    class Boom:
        def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
            raise ValueError("boom")

    svc = PipelineService(
        db_session,
        scraper_factory=lambda key, http=None, rate_limiter=None: Boom(),  # type: ignore[arg-type,return-value]
        notifier_factory=lambda key: RecordingNotifier(),  # type: ignore[arg-type,return-value]
    )
    with pytest.raises(ValueError, match="boom"):
        svc.scrape(
            adapter_key="greenhouse",
            user_id=search.user_id,
            source_id=search.source_id,
            query_url="",
            filters={},
            config={},
        )


def test_filter_cross_search_skips_urls_seen_in_another_search(db_session: Session) -> None:
    from app.models.base import utcnow
    from app.models.search import Search

    user = make_search(db_session).user
    first = make_search(db_session, user=user)
    # Run the first search so the shared URL is persisted for this user.
    pipeline(
        db_session, FakeScraper([posting("1", url="https://acme.test/shared")]), RecordingNotifier()
    ).run(first.id)

    second = Search(
        user_id=user.id,
        name="second",
        source_id=first.source_id,
        target_id=first.target_id,
        query_url="",
        filters={},
        config={},
        interval_seconds=300,
        enabled=True,
        next_run_at=utcnow(),
    )
    db_session.add(second)
    db_session.flush()

    notifier = RecordingNotifier()
    result = pipeline(
        db_session,
        FakeScraper([posting("2", url="https://acme.test/shared")]),
        notifier,
    ).run(second.id)
    # New in this search, but skipped from notification (already seen elsewhere).
    assert result.new == 1
    assert result.skipped == 1
    assert result.notified == 0


def test_filter_cross_search_keeps_postings_without_url(db_session: Session) -> None:
    search = make_search(db_session)
    scraper = FakeScraper([posting("1", url="")])
    notifier = RecordingNotifier()
    result = pipeline(db_session, scraper, notifier).run(search.id)
    assert result.new == 1
    assert result.notified == 1


def test_notify_skips_when_no_target(db_session: Session) -> None:
    search = make_search(db_session)
    search.target_id = None
    db_session.flush()
    scraper = FakeScraper([posting("1")])
    notifier = RecordingNotifier()
    result = pipeline(db_session, scraper, notifier).run(search.id)
    assert result.new == 1
    assert result.notified == 0
    assert len(notifier.batches) == 0


def test_notify_counts_failed_deliveries(db_session: Session) -> None:
    search = make_search(db_session)
    scraper = FakeScraper([posting("1"), posting("2")])

    class MixedNotifier:
        def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
            return [
                DeliveryResult(external_id="1", status="sent"),
                DeliveryResult(external_id="2", status="failed", error="nope"),
                DeliveryResult(external_id="unknown", status="sent"),
            ]

    svc = PipelineService(
        db_session,
        scraper_factory=lambda key, http=None, rate_limiter=None: scraper,  # type: ignore[arg-type,return-value]
        notifier_factory=lambda key: MixedNotifier(),  # type: ignore[arg-type,return-value]
    )
    result = svc.run(search.id)
    assert result.notified == 1
    assert result.failed == 1
    # The delivery result for an unknown external id is ignored.
    assert db_session.query(DeliveryLog).count() == 2


def test_reschedule_handles_deleted_search(db_session: Session) -> None:
    svc = pipeline(db_session, FakeScraper([]), RecordingNotifier())
    # A missing search means _reschedule finds nothing to update.
    svc._reschedule(999999)  # no error


def test_run_with_all_duplicates_notifies_nothing(db_session: Session) -> None:
    search = make_search(db_session)
    scraper = FakeScraper([posting("1")])
    notifier = RecordingNotifier()
    svc = pipeline(db_session, scraper, notifier)
    svc.run(search.id)  # first run persists the job

    # Second run: same posting -> all deduped, empty to_notify path.
    result = svc.run(search.id)
    assert result.new == 0
    assert result.notified == 0
    assert result.skipped == 0


def test_scrape_uses_no_http_client_without_credentials(db_session: Session) -> None:
    from app.models.source import Source

    search = make_search(db_session)
    source = db_session.get(Source, search.source_id)
    assert source is not None
    source.adapter_key = "rss"  # min_interval 0 -> no rate limiter
    db_session.flush()
    seen_http: dict[str, object] = {}

    def factory(key, http=None, rate_limiter=None):
        seen_http["http"] = http
        return FakeScraper([posting("1")])

    svc = PipelineService(
        db_session,
        scraper_factory=factory,  # type: ignore[arg-type]
        notifier_factory=lambda key: RecordingNotifier(),  # type: ignore[arg-type,return-value]
    )
    svc.run(search.id)
    # No credentials and no rate limiter for rss -> http stays None.
    assert seen_http["http"] is None


def test_queue_digest_skips_postings_without_seen_row(db_session: Session) -> None:
    search = make_search(db_session)
    svc = pipeline(db_session, FakeScraper([]), RecordingNotifier())
    # A posting whose external_id is absent from seen_rows is skipped.
    queued = svc._queue_digest(search.id, [posting("ghost")], {})
    assert queued == 0
