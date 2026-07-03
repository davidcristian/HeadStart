from app.scrapers.types import JobPosting
from app.summarizers import SummaryContext, get_summarizer
from app.summarizers.adapters.heuristic import HeuristicSummarizer


def _job(**kwargs: object) -> JobPosting:
    base = {
        "external_id": "1",
        "title": "Senior Python Engineer",
        "company": "ACME",
        "location": "Berlin (Remote)",
    }
    base.update(kwargs)
    return JobPosting(**base)  # type: ignore[arg-type]


def test_registry_resolves_heuristic() -> None:
    assert isinstance(get_summarizer("heuristic"), HeuristicSummarizer)


def test_blurb_mentions_matched_keywords() -> None:
    ctx = SummaryContext(filters={"keywords": "python, senior"})
    (blurb,) = HeuristicSummarizer().summarize(ctx, [_job()])
    assert "python" in blurb
    assert "senior" in blurb
    assert blurb.startswith("Matches your search")


def test_blurb_reports_workplace_and_location() -> None:
    ctx = SummaryContext(filters={"workplace": "remote", "location": "berlin"})
    (blurb,) = HeuristicSummarizer().summarize(ctx, [_job()])
    assert "remote role" in blurb
    assert "Berlin" in blurb


def test_blurb_falls_back_without_matching_filters() -> None:
    ctx = SummaryContext(search_name="Backend roles", filters={})
    (blurb,) = HeuristicSummarizer().summarize(ctx, [_job()])
    assert "Backend roles" in blurb
    assert "Senior Python Engineer" in blurb


def test_blurb_ignores_unmatched_keywords() -> None:
    ctx = SummaryContext(filters={"keywords": "golang"})
    (blurb,) = HeuristicSummarizer().summarize(ctx, [_job()])
    # No keyword matched, so it should fall back rather than claim a match.
    assert "golang" not in blurb
    assert blurb.endswith(".")


def test_summarize_aligns_one_blurb_per_job() -> None:
    ctx = SummaryContext(filters={})
    jobs = [_job(external_id="1"), _job(external_id="2", title="Data Scientist")]
    blurbs = HeuristicSummarizer().summarize(ctx, jobs)
    assert len(blurbs) == 2
    assert "Data Scientist" in blurbs[1]


def test_workplace_and_location_filters_without_a_match_fall_back() -> None:
    # workplace=onsite but job is remote; location=paris but job is in Berlin.
    ctx = SummaryContext(
        search_name="Remote roles",
        filters={"workplace": "onsite", "location": "paris"},
    )
    (blurb,) = HeuristicSummarizer().summarize(ctx, [_job(location="Berlin (Remote)")])
    assert "onsite role" not in blurb
    assert "in " not in blurb
    assert "Remote roles" in blurb


def test_keywords_from_list_are_deduplicated() -> None:
    ctx = SummaryContext(filters={"keywords_include": ["python", "python", 123]})
    (blurb,) = HeuristicSummarizer().summarize(ctx, [_job(title="Python Python Engineer")])
    assert blurb.count("python") == 1


def test_hybrid_workplace_is_recognized() -> None:
    ctx = SummaryContext(filters={"workplace": "hybrid"})
    (blurb,) = HeuristicSummarizer().summarize(ctx, [_job(location="Berlin (Hybrid)")])
    assert "hybrid role" in blurb


def test_onsite_workplace_is_recognized() -> None:
    ctx = SummaryContext(filters={"workplace": "on-site"})
    (blurb,) = HeuristicSummarizer().summarize(ctx, [_job(location="Berlin on-site")])
    assert "onsite role" in blurb


def test_infer_workplace_returns_none_without_signals() -> None:
    # workplace filter forces _infer_workplace to run, but the job has no
    # remote/hybrid/onsite signal in title or location.
    ctx = SummaryContext(search_name="X", filters={"workplace": "remote"})
    (blurb,) = HeuristicSummarizer().summarize(ctx, [_job(title="Data Analyst", location="Berlin")])
    assert "remote role" not in blurb
    assert blurb.startswith("New match for 'X'")


def test_unknown_workplace_token_is_ignored() -> None:
    # A workplace token that maps to nothing leaves the workplaces set empty.
    ctx = SummaryContext(search_name="X", filters={"workplace": "flexible"})
    (blurb,) = HeuristicSummarizer().summarize(ctx, [_job(location="Berlin")])
    assert "workplace" not in blurb
    assert blurb.startswith("New match for 'X'")
