"""Regression: pyproject floors match majors CI actually tests (XCT-23)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PYPROJECT = _REPO_ROOT / "backend" / "pyproject.toml"
_DEPLOYMENT_DOC = _REPO_ROOT / "docs" / "modules" / "deployment.md"
_LOCKFILES = (
    _REPO_ROOT / "backend" / "requirements.txt",
    _REPO_ROOT / "backend" / "requirements-dev.txt",
    _REPO_ROOT / "backend" / "requirements-playwright.txt",
)

# Majors exercised by the hashed lockfiles / CI — floors must not lag these.
_MIN_FLOORS: dict[str, tuple[int, ...]] = {
    "celery": (5, 6),
    "redis": (6, 0),
    "httpx": (0, 28),
    "cryptography": (49, 0),
    "stripe": (15, 0),
}


def _parse_floor(text: str, name: str) -> tuple[int, ...]:
    """Extract the ``name>=X.Y`` (optional patch) floor from pyproject.toml."""
    match = re.search(rf'"{re.escape(name)}(?:\[[^\]]+\])?>=(\d+(?:\.\d+)*)"', text)
    assert match is not None, f"pyproject.toml must declare {name}>=…"
    return tuple(int(part) for part in match.group(1).split("."))


def _parse_lock_pin(text: str, name: str) -> tuple[int, ...]:
    match = re.search(rf"^{re.escape(name)}==(\d+(?:\.\d+)*)", text, re.M)
    assert match is not None, f"lockfile must pin {name}==…"
    return tuple(int(part) for part in match.group(1).split("."))


def test_pyproject_floors_match_tested_majors() -> None:
    """Declared support must not advertise untested older majors (XCT-23)."""
    text = _PYPROJECT.read_text(encoding="utf-8")
    for name, minimum in _MIN_FLOORS.items():
        floor = _parse_floor(text, name)
        assert floor >= minimum, f"{name} floor {floor} below tested {minimum}"


def test_lockfile_pins_satisfy_pyproject_floors() -> None:
    """Hash-locked pins must meet the floors so CI cannot drift below them."""
    floors_text = _PYPROJECT.read_text(encoding="utf-8")
    for lock in _LOCKFILES:
        text = lock.read_text(encoding="utf-8")
        for name in _MIN_FLOORS:
            floor = _parse_floor(floors_text, name)
            pin = _parse_lock_pin(text, name)
            assert pin >= floor, f"{lock.name}: {name} pin {pin} below floor {floor}"


def test_deployment_doc_records_floor_policy() -> None:
    """Operators need the floor↔lock contract documented next to lockfiles."""
    text = _DEPLOYMENT_DOC.read_text(encoding="utf-8")
    assert "just lock-backend" in text
    assert "floors" in text.lower()
    assert "XCT-23" in text or "tested majors" in text.lower()
