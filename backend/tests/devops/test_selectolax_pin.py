"""Regression: selectolax stays reviewed-floor + hash-pinned (XCT-22)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PYPROJECT = _REPO_ROOT / "backend" / "pyproject.toml"
_SCRAPERS_DOC = _REPO_ROOT / "docs" / "modules" / "scrapers.md"
_LOCKFILES = (
    _REPO_ROOT / "backend" / "requirements.txt",
    _REPO_ROOT / "backend" / "requirements-dev.txt",
    _REPO_ROOT / "backend" / "requirements-playwright.txt",
)

# Reviewed floor for the untrusted-HTML parser (must match pyproject + lock).
_MIN_FLOOR = (0, 4, 10)


def _parse_selectolax_floor(text: str) -> tuple[int, int, int]:
    match = re.search(r'"selectolax>=(\d+)\.(\d+)\.(\d+)"', text)
    assert match is not None, "pyproject.toml must declare selectolax>=X.Y.Z"
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def test_pyproject_selectolax_floor_is_reviewed_version() -> None:
    """Manifest floor must not lag the reviewed lock pin (XCT-22)."""
    floor = _parse_selectolax_floor(_PYPROJECT.read_text(encoding="utf-8"))
    assert floor >= _MIN_FLOOR, f"selectolax floor {floor} below reviewed {_MIN_FLOOR}"


def test_lockfiles_pin_selectolax_with_hashes() -> None:
    """Builds must install a hash-pinned selectolax, not a floating resolve."""
    for lock in _LOCKFILES:
        text = lock.read_text(encoding="utf-8")
        assert re.search(
            r"^selectolax==\d+\.\d+\.\d+ \\?$", text, re.M
        ), f"{lock.name} must pin selectolax==X.Y.Z"
        # The pin line is followed by one or more --hash= lines before the next pkg.
        pin_idx = text.index("selectolax==")
        window = text[pin_idx : pin_idx + 800]
        assert "--hash=sha256:" in window, f"{lock.name} selectolax pin lacks hashes"


def test_scrapers_doc_records_selectolax_pin_and_lxml_fallback() -> None:
    """Operators need the pin policy and lxml fallback plan in module docs."""
    text = _SCRAPERS_DOC.read_text(encoding="utf-8")
    assert "selectolax>=0.4.10" in text or "selectolax>=" in text
    assert "lxml" in text.lower()
    assert "just lock-backend" in text
