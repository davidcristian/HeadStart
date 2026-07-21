"""Regression: the text gate bans dashes and tracker ids, but spares real data.

The allowlist is the load-bearing part. Job boards emit " — " in page titles and
postings separate salary bounds with "–", so those literals are inputs, not
prose. A gate that "cleaned" them would break scraping while looking green.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "check_text.sh"


def _run() -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(_SCRIPT)], capture_output=True, text=True, cwd=_REPO_ROOT)


def test_repo_passes_its_own_text_gate() -> None:
    """The tree must satisfy the rule it now enforces."""
    proc = _run()
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize(
    "injected",
    [
        pytest.param("prose with an em dash — here", id="em-dash"),
        pytest.param("prose with an en dash – here", id="en-dash"),
        pytest.param("a tracker id OPS-99 here", id="tracker-id"),
        pytest.param("a workstream id WS42 here", id="workstream-id"),
        # An escape renders the dash at runtime while hiding it from a grep,
        # so the gate must treat it as the dash it is.
        pytest.param("an escaped \\u2014 dash", id="unicode-escape"),
    ],
)
def test_gate_detects_each_violation(injected: str) -> None:
    """Inject into a tracked, non-allowlisted file and require a failure."""
    target = _REPO_ROOT / "docs" / "runbook.md"
    backup = target.read_text(encoding="utf-8")
    try:
        target.write_text(backup + "\n" + injected + "\n", encoding="utf-8")
        proc = _run()
        assert proc.returncode != 0, f"gate missed: {injected}"
        assert "runbook.md" in proc.stderr
    finally:
        target.write_text(backup, encoding="utf-8")
    # The gate must go quiet again once the violation is gone, or it is
    # failing for some unrelated reason and proves nothing.
    assert _run().returncode == 0


def test_gate_sees_untracked_files() -> None:
    """git grep skips untracked files, so a new file's violations would be
    invisible until committed and `just check` would read green on a dirty tree."""
    probe = _REPO_ROOT / "docs" / "_untracked_gate_probe.md"
    assert not probe.exists()
    try:
        probe.write_text("prose with an em dash — here\n", encoding="utf-8")
        proc = _run()
        assert proc.returncode != 0, "gate ignored an untracked file"
        assert "_untracked_gate_probe" in proc.stderr
    finally:
        probe.unlink(missing_ok=True)
    assert _run().returncode == 0


def test_allowlist_is_not_a_blanket_exemption() -> None:
    """An over-broad entry silently reopens the rule, so keep the list narrow."""
    text = (_REPO_ROOT / "scripts" / "check_text.sh").read_text(encoding="utf-8")
    for entry in ("'backend/'", "'backend/app'", "'.py'", "'docs/'", "'/'"):
        assert entry not in text, f"allowlist entry too broad: {entry}"


def test_allowlist_spares_external_data_parsers() -> None:
    """The page-title matchers keep the dash the boards actually emit."""
    apple = (_REPO_ROOT / "backend" / "app" / "scrapers" / "url_detect_apple.py").read_text(
        encoding="utf-8"
    )
    assert "—" in apple, "matcher must keep the literal the board emits"
    assert _run().returncode == 0, "allowlisted parser dash must not fail the gate"


def test_allowlist_spares_captured_fixtures() -> None:
    """Captured HTML is evidence; editing it makes the fixture lie."""
    fixture = _REPO_ROOT / "backend" / "tests" / "fixtures" / "google_careers_results.html"
    assert "—" in fixture.read_text(encoding="utf-8")
    assert _run().returncode == 0


def test_salary_regex_keeps_every_separator_it_parses() -> None:
    """Postings use -, en dash or em dash between bounds; all must stay matchable."""
    text = (_REPO_ROOT / "backend" / "app" / "services" / "compensation_amounts.py").read_text(
        encoding="utf-8"
    )
    assert "–" in text and "—" in text


def test_gate_is_wired_into_lint() -> None:
    """A gate nobody runs is documentation. lint.sh must invoke it."""
    lint = (_REPO_ROOT / "scripts" / "lint.sh").read_text(encoding="utf-8")
    assert "check_text.sh" in lint


def test_commit_msg_gate_is_installed_as_a_hook_type() -> None:
    """pre-commit only installs pre-commit hooks unless commit-msg is declared."""
    cfg = (_REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "default_install_hook_types" in cfg
    assert "commit-msg" in cfg
    assert "check_commit_msg.sh" in cfg


def test_shellcheck_accepts_the_new_gates() -> None:
    """The repo runs shellcheck; the gates must not be the thing that breaks it."""
    if shutil.which("shellcheck") is None:
        pytest.skip("shellcheck not installed")
    proc = subprocess.run(
        [
            "shellcheck",
            "-x",
            "-S",
            "warning",
            str(_SCRIPT),
            str(_REPO_ROOT / "scripts" / "check_commit_msg.sh"),
        ],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stdout
