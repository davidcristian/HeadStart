"""Regression: targeted lock upgrades stay inside the lockfile that owns them.

`pip-compile --upgrade-package NAME` does not merely bump NAME, it ADDS it when
the file does not already pin it. Asking for a dev-only tool while compiling the
runtime lock therefore rewrites production dependencies: `--upgrade-package
pre-commit` dragged pre-commit plus virtualenv, nodeenv and identify into
`requirements.txt`. The script filters each request to the files that already
pin it, and `--dry-run` exposes that decision without a network round trip.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "lock-backend.sh"
_RUNTIME_LOCK = _REPO_ROOT / "backend" / "requirements.txt"
_DEV_LOCK = _REPO_ROOT / "backend" / "requirements-dev.txt"


def _plan(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the planner. --dry-run writes nothing, so this is safe in a test."""
    return subprocess.run(
        ["bash", str(_SCRIPT), "--dry-run", *args],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )


def _line_for(output: str, lock: str) -> str:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{lock}:"):
            return stripped
    raise AssertionError(f"no plan line for {lock} in:\n{output}")


def test_dev_only_package_never_reaches_the_runtime_lock() -> None:
    """The leak this scoping exists to prevent."""
    proc = _plan("--upgrade-package", "pre-commit")
    assert proc.returncode == 0, proc.stderr
    assert "pre-commit" not in _line_for(proc.stdout, "requirements.txt")
    assert "pre-commit" not in _line_for(proc.stdout, "requirements-playwright.txt")
    assert "pre-commit" in _line_for(proc.stdout, "requirements-dev.txt")


def test_the_leak_premise_still_holds() -> None:
    """If pre-commit ever becomes a runtime dep the test above proves nothing."""
    assert "pre-commit==" not in _RUNTIME_LOCK.read_text(encoding="utf-8")
    assert "pre-commit==" in _DEV_LOCK.read_text(encoding="utf-8")


def test_shared_package_reaches_every_lock_that_pins_it() -> None:
    """Scoping must not under-apply: fastapi is in all three lockfiles."""
    proc = _plan("--upgrade-package", "fastapi")
    assert proc.returncode == 0, proc.stderr
    for lock in ("requirements.txt", "requirements-dev.txt", "requirements-playwright.txt"):
        assert "fastapi" in _line_for(proc.stdout, lock)


def test_bare_run_keeps_existing_pins() -> None:
    """A plain regenerate must not move pins, or every run becomes an upgrade."""
    proc = _plan()
    assert proc.returncode == 0, proc.stderr
    for lock in ("requirements.txt", "requirements-dev.txt", "requirements-playwright.txt"):
        assert "keep existing pins" in _line_for(proc.stdout, lock)


def test_upgrade_all_applies_everywhere() -> None:
    proc = _plan("--upgrade")
    assert proc.returncode == 0, proc.stderr
    for lock in ("requirements.txt", "requirements-dev.txt", "requirements-playwright.txt"):
        assert "--upgrade" in _line_for(proc.stdout, lock)


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("pre-commit", id="canonical"),
        pytest.param("Pre_Commit", id="mixed-case-underscore"),
        pytest.param("PRE.COMMIT", id="upper-dot"),
    ],
)
def test_package_names_are_matched_pep503_style(name: str) -> None:
    """. _ and - are equivalent in a requirement name, and case is ignored."""
    proc = _plan("--upgrade-package", name)
    assert proc.returncode == 0, proc.stderr
    assert name in _line_for(proc.stdout, "requirements-dev.txt")
    assert name not in _line_for(proc.stdout, "requirements.txt")


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["--upgrade-package", "fastpai"], id="typo"),
        pytest.param(["--upgrade", "--upgrade-package", "fastapi"], id="mutually-exclusive"),
        pytest.param(["--frobnicate"], id="unknown-flag"),
        pytest.param(["--upgrade-package"], id="missing-value"),
    ],
)
def test_bad_invocations_fail_loudly(args: list[str]) -> None:
    """A misspelled name must not read as a silent no-op upgrade."""
    proc = subprocess.run(
        ["bash", str(_SCRIPT), *args], capture_output=True, text=True, cwd=_REPO_ROOT
    )
    assert proc.returncode != 0, proc.stdout
    assert "ERROR" in proc.stderr


def test_shellcheck_accepts_the_script() -> None:
    if shutil.which("shellcheck") is None:
        pytest.skip("shellcheck not installed")
    proc = subprocess.run(
        ["shellcheck", "-x", "-S", "warning", str(_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stdout
