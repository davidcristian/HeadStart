"""Unit tests for LinkedIn apply route resolution (linkedin_route)."""

from __future__ import annotations

from _pytest.monkeypatch import MonkeyPatch

from app.appliers.adapters.linkedin_detail import LinkedInJobDetail
from app.appliers.adapters.linkedin_route import resolve_apply_route

# --- route resolution edge cases ---------------------------------------------


def _detail(**overrides: object) -> LinkedInJobDetail:
    base: dict[str, object] = {
        "job_id": "1",
        "title": "T",
        "company": "C",
        "reference_id": None,
        "tracking_id": None,
        "easy_apply": False,
        "offsite_apply": False,
        "external_apply_url": None,
        "expired": False,
    }
    base.update(overrides)
    return LinkedInJobDetail(**base)  # type: ignore[arg-type]


def test_resolve_apply_route_expired() -> None:
    route = resolve_apply_route(_detail(expired=True))
    assert route.kind == "unsupported"
    assert "expired" in (route.reason or "")


def test_resolve_apply_route_external_registered_ats() -> None:
    route = resolve_apply_route(
        _detail(external_apply_url="https://boards.greenhouse.io/acme/jobs/5501001")
    )
    assert route.kind == "external_ats"
    assert route.adapter_key == "greenhouse"


def test_resolve_apply_route_external_ats_without_adapter(monkeypatch: MonkeyPatch) -> None:
    # An ATS URL that parses to a known target whose adapter is not registered.
    import app.appliers.adapters.linkedin_route as route_module

    monkeypatch.setattr(route_module, "has_applier", lambda key: False)
    route = resolve_apply_route(
        _detail(external_apply_url="https://boards.greenhouse.io/acme/jobs/5501001")
    )
    assert route.kind == "unsupported"
    assert route.adapter_key == "greenhouse"
    assert "no apply adapter" in (route.reason or "")


def test_resolve_apply_route_external_unrecognized_url() -> None:
    route = resolve_apply_route(
        _detail(external_apply_url="https://random-company.example/careers/apply")
    )
    assert route.kind == "unsupported"
    assert "not a supported ATS" in (route.reason or "")


def test_resolve_apply_route_easy_apply() -> None:
    route = resolve_apply_route(_detail(easy_apply=True))
    assert route.kind == "linkedin_hosted"
    assert route.adapter_key == "linkedin"


def test_resolve_apply_route_offsite_without_url() -> None:
    route = resolve_apply_route(_detail(offsite_apply=True))
    assert route.kind == "unsupported"
    assert "offsite apply URL was not found" in (route.reason or "")


def test_resolve_apply_route_no_signal() -> None:
    route = resolve_apply_route(_detail())
    assert route.kind == "unsupported"
    assert "no Easy Apply button" in (route.reason or "")
