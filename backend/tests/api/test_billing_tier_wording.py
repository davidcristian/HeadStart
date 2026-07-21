"""Regression: billing.md tier count matches the paid enumeration."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BILLING_DOC = _REPO_ROOT / "docs" / "modules" / "billing.md"
_PLANS = _REPO_ROOT / "backend" / "app" / "core" / "plans.py"


def test_billing_md_intro_matches_three_paid_tiers() -> None:
    """Intro must not say 'four … tiers (Starter, Plus, Pro)'."""
    text = _BILLING_DOC.read_text(encoding="utf-8")
    assert "four public tiers (Starter, Plus, Pro)" not in text
    assert "three paid tiers (Starter, Plus, Pro)" in text
    # Plans section still documents Free + the three paid tiers.
    assert "| Free |" in text
    assert "| Starter |" in text
    assert "| Plus |" in text
    assert "| Pro |" in text


def test_plans_module_still_defines_four_plan_ids() -> None:
    """Guard against doc-only drift if the plan matrix shrinks."""
    src = _PLANS.read_text(encoding="utf-8")
    assert 'VALID_PLANS: frozenset[str] = frozenset({"free", "starter", "plus", "pro"})' in src
