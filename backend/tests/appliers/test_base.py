"""Tests for the applier base class and registry."""

import pytest

from app.appliers.base import (
    Applier,
    available_appliers,
    get_applier,
    has_applier,
    register_applier,
)
from app.appliers.types import ApplyContext, ApplyResult


def test_get_applier_unknown_key_raises_keyerror() -> None:
    with pytest.raises(KeyError, match="No applier registered for 'does-not-exist'"):
        get_applier("does-not-exist")


def test_available_appliers_lists_registered_keys() -> None:
    keys = available_appliers()
    assert "ashby" in keys
    assert keys == sorted(keys)


def test_has_applier_true_and_false() -> None:
    assert has_applier("ashby")
    assert not has_applier("does-not-exist")


def test_register_applier_rejects_duplicate_key() -> None:
    @register_applier("test-base-dup")
    class _First(Applier):
        def apply(self, ctx: ApplyContext) -> ApplyResult:
            return ApplyResult(status="dry_run")

    with pytest.raises(ValueError, match="already registered"):

        @register_applier("test-base-dup")
        class _Second(Applier):
            def apply(self, ctx: ApplyContext) -> ApplyResult:
                return ApplyResult(status="dry_run")


def test_register_applier_idempotent_for_same_class() -> None:
    @register_applier("test-base-idempotent")
    class _Only(Applier):
        def apply(self, ctx: ApplyContext) -> ApplyResult:
            return ApplyResult(status="dry_run")

    # Re-registering the exact same class is a no-op and must not raise.
    register_applier("test-base-idempotent")(_Only)
    assert has_applier("test-base-idempotent")


def test_applier_defaults_to_real_http_client() -> None:
    @register_applier("test-base-default-http")
    class _Default(Applier):
        def apply(self, ctx: ApplyContext) -> ApplyResult:
            return ApplyResult(status="dry_run")

    assert _Default().http is not None


def test_apply_context_dry_run_defaults_to_true() -> None:
    """Omitting dry_run must preview, never live-submit by accident."""
    from app.schemas.profile import ProfileData

    ctx = ApplyContext(
        job_external_id="1",
        job_title="Role",
        company="Co",
        job_url="https://example.com/jobs/1",
        profile=ProfileData(full_name="Ada Lovelace", email="a@b.com"),
    )
    assert ctx.dry_run is True
    assert (
        ApplyContext(
            job_external_id="1",
            job_title="Role",
            company="Co",
            job_url="https://example.com/jobs/1",
            profile=ProfileData(full_name="Ada Lovelace", email="a@b.com"),
            dry_run=False,
        ).dry_run
        is False
    )
