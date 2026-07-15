"""Regression: CI failure Slack notify guard can see the webhook (OPS-21)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CI_YML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _notify_job_block(text: str) -> str:
    """Return the `notify:` job body (through EOF or next top-level key)."""
    match = re.search(r"(?ms)^  notify:\n(.*?)(?=^  [a-z]|\Z)", text)
    assert match is not None, "ci.yml is missing the notify job"
    return match.group(1)


def test_ci_slack_webhook_env_is_job_scoped() -> None:
    """SLACK_WEBHOOK_URL must be set at job level so step `if: env.*` works."""
    text = _CI_YML.read_text(encoding="utf-8")
    job = _notify_job_block(text)
    assert "SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}" in job
    # Job-level env precedes steps; step-only env would not feed the step `if`.
    env_idx = job.find("env:")
    steps_idx = job.find("steps:")
    assert 0 <= env_idx < steps_idx, "notify job must declare env before steps"
    assert "if: ${{ env.SLACK_WEBHOOK_URL != '' }}" in job


def test_ci_notify_step_does_not_rely_on_step_level_webhook_env() -> None:
    """Step-level env alone must not gate the notify step (OPS-21 bug)."""
    text = _CI_YML.read_text(encoding="utf-8")
    job = _notify_job_block(text)
    steps = job[job.find("steps:") :]
    # A step that both maps the secret under `env:` and gates on env.SLACK_*
    # would reintroduce the always-empty guard.
    broken = re.search(
        r"(?ms)if:\s*\$\{\{\s*env\.SLACK_WEBHOOK_URL\s*!=\s*''\s*\}\}.*?env:\s*\n"
        r"\s*SLACK_WEBHOOK_URL:\s*\$\{\{\s*secrets\.SLACK_WEBHOOK_URL\s*\}\}",
        steps,
    )
    assert broken is None, "notify step must not gate on step-scoped SLACK_WEBHOOK_URL"
