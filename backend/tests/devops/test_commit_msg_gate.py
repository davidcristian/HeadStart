"""Regression: the commit message gate rejects what the conventions ban.

Every rule here drifted while the docs were the only thing enforcing it, so
these tests exist to keep the gate honest rather than to restate the rules.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "check_commit_msg.sh"


def _run(msg: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    f = tmp_path / "COMMIT_EDITMSG"
    f.write_text(msg, encoding="utf-8")
    return subprocess.run(
        ["bash", str(_SCRIPT), str(f)],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )


GOOD = [
    "feat(scrapers): add SuccessFactors OData apply adapter",
    "fix: widen UID columns to BigInteger",
    "chore: drop dead tracker ids from source",
    "docs(auth): document token rotation\n\nA longer body explaining why.",
]

BAD = [
    pytest.param("style: sort imports", id="type-not-allowed"),
    pytest.param("Initial commit", id="no-conventional-prefix"),
    pytest.param("a11y(frontend): trap focus", id="a11y-not-a-type"),
    pytest.param("feat: add adapter (#285)", id="pr-ref-suffix"),
    pytest.param("feat: add adapter\n\nShipped with PR #34.", id="pr-ref-body"),
    pytest.param("feat: add portal catalog batch 10", id="batch-number"),
    pytest.param("fix: repair rendering (audit WS26)", id="workstream-id"),
    pytest.param("fix: cap portal selection (FRO-07)", id="tracker-id"),
    pytest.param("feat: ship Phase 31 presets", id="phase-number"),
    pytest.param("docs: update the roadmap", id="roadmap-word"),
    pytest.param("docs: drain the backlog", id="backlog-word"),
    pytest.param("fix: stop overflow — widen columns", id="em-dash"),
    pytest.param("test: cover 2019–2021 ranges", id="en-dash"),
]


@pytest.mark.parametrize("msg", GOOD)
def test_gate_accepts_conforming_messages(msg: str, tmp_path: Path) -> None:
    """A message that follows the conventions must pass."""
    assert _run(msg, tmp_path).returncode == 0


@pytest.mark.parametrize("msg", BAD)
def test_gate_rejects_violations(msg: str, tmp_path: Path) -> None:
    """Each banned shape must be rejected; a gate that cannot fail is noise."""
    assert _run(msg, tmp_path).returncode != 0


def test_gate_ignores_git_comment_lines(tmp_path: Path) -> None:
    """git's editor template is comments; they must not trip the rules."""
    msg = "feat: add adapter\n\n# Please enter the commit message. Phase 3 (#12) —\n"
    assert _run(msg, tmp_path).returncode == 0


def test_gate_allows_an_empty_message(tmp_path: Path) -> None:
    """An empty message aborts the commit anyway; the gate must not mask that."""
    assert _run("\n# comment only\n", tmp_path).returncode == 0


def test_unresolvable_range_fails_loudly(tmp_path: Path) -> None:
    """A bad range must not read as zero commits and pass having checked nothing."""
    proc = subprocess.run(
        ["bash", str(_SCRIPT), "--range", "no-such-ref~1..no-such-ref"],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    assert proc.returncode != 0
    assert "cannot resolve range" in proc.stderr


def test_range_mode_reports_how_many_it_inspected() -> None:
    """A silently empty range otherwise reads identically to a clean one."""
    proc = subprocess.run(
        ["bash", str(_SCRIPT), "--range", "HEAD~3..HEAD"],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    assert proc.returncode == 0
    assert "Inspected" in proc.stdout


def test_current_history_passes_its_own_gate() -> None:
    """The cleaned history must satisfy the rule it now enforces."""
    proc = subprocess.run(
        ["bash", str(_SCRIPT), "--range", "HEAD~20..HEAD"],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
