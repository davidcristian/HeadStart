"""Coverage for the notifier registry and base class."""

import pytest

from app.notifiers.base import (
    Notifier,
    available_notifiers,
    get_notifier,
    register_notifier,
)
from app.notifiers.types import DeliveryResult, NotifyContext
from app.scrapers.types import JobPosting


def test_register_rejects_duplicate_key_for_different_class() -> None:
    @register_notifier("dup_key_test")
    class _First(Notifier):
        def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
            return []

    with pytest.raises(ValueError, match="already registered"):

        @register_notifier("dup_key_test")
        class _Second(Notifier):
            def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
                return []


def test_register_is_idempotent_for_same_class() -> None:
    @register_notifier("idempotent_key_test")
    class _Only(Notifier):
        def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
            return []

    # Re-registering the same class under the same key must not raise.
    register_notifier("idempotent_key_test")(_Only)


def test_get_notifier_unknown_key_raises() -> None:
    with pytest.raises(KeyError, match="No notifier registered"):
        get_notifier("definitely-not-a-real-notifier")


def test_available_notifiers_lists_built_ins() -> None:
    names = available_notifiers()
    assert {"telegram", "discord", "email", "slack", "ntfy", "webhook"}.issubset(set(names))
    assert names == sorted(names)
