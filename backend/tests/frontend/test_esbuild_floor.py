"""Regression: frontend lockfile pins esbuild past GHSA-67mh-4wv8-2f99."""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PACKAGE_JSON = _REPO_ROOT / "frontend" / "package.json"
_LOCKFILE = _REPO_ROOT / "frontend" / "package-lock.json"

# Patched floor for the esbuild dev-server CORS SSRF advisory.
_MIN_ESBUILD = (0, 25, 0)


def _parse_semver(version: str) -> tuple[int, int, int]:
    """Parse a leading major.minor.patch from an npm version string."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
    assert match is not None, f"unparseable esbuild version: {version!r}"
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def test_package_json_overrides_esbuild_past_ssrf_floor() -> None:
    """package.json must force esbuild >=0.25 even when vite's range is looser."""
    pkg = json.loads(_PACKAGE_JSON.read_text(encoding="utf-8"))
    overrides = pkg.get("overrides") or {}
    floor = overrides.get("esbuild")
    assert isinstance(floor, str), "missing overrides.esbuild"
    assert floor.lstrip("^~>= ").startswith("0.25"), floor


def test_lockfile_resolves_esbuild_past_ssrf_floor() -> None:
    """Every locked esbuild package must be >=0.25.0 (no nested 0.21.x)."""
    lock = json.loads(_LOCKFILE.read_text(encoding="utf-8"))
    packages = lock.get("packages") or {}
    found = False
    for path, meta in packages.items():
        name = meta.get("name")
        if name != "esbuild" and not path.endswith("/esbuild") and path != "node_modules/esbuild":
            continue
        version = meta.get("version")
        assert isinstance(version, str), f"esbuild entry missing version: {path}"
        assert _parse_semver(version) >= _MIN_ESBUILD, f"{path} pins esbuild {version}"
        found = True
    assert found, "no esbuild entries in package-lock.json"
