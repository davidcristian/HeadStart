"""Unit tests for plan_limit_checks helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import PlanLimitError
from app.services.plan_limit_checks import (
    require_notifier,
    require_scraper,
    require_under_cap,
)


def test_require_under_cap_allows_below_maximum() -> None:
    require_under_cap("free", code="search_limit", resource="searches", current=0, maximum=3)


def test_require_under_cap_raises_at_maximum() -> None:
    with pytest.raises(PlanLimitError) as exc:
        require_under_cap("free", code="search_limit", resource="searches", current=3, maximum=3)
    assert exc.value.code == "search_limit"
    assert exc.value.limit == 3


def test_require_scraper_allows_free_adapter() -> None:
    require_scraper("free", "greenhouse")


def test_require_scraper_blocks_premium_on_free() -> None:
    with pytest.raises(PlanLimitError) as exc:
        require_scraper("free", "indeed")
    assert exc.value.code == "premium_scraper"


def test_require_notifier_allows_ntfy() -> None:
    require_notifier("free", "ntfy")


def test_require_notifier_blocks_webhook_on_free() -> None:
    with pytest.raises(PlanLimitError) as exc:
        require_notifier("free", "webhook")
    assert exc.value.code == "premium_notifier"
