"""Regression: backend Dockerfile installs deps before copying app (OPS-28)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCKERFILE = _REPO_ROOT / "backend" / "Dockerfile"


def _base_stage(dockerfile: str) -> str:
    """Return the base stage body (before the first named FROM after base)."""
    match = re.search(
        r"FROM python:3\.12-slim AS base\n(.*?)(?=\nFROM )",
        dockerfile,
        flags=re.DOTALL,
    )
    assert match is not None, "base stage not found in backend/Dockerfile"
    return match.group(1)


def test_dockerfile_installs_hashed_deps_before_copying_app() -> None:
    """Third-party deps must install before COPY app so source edits keep the cache."""
    text = _DOCKERFILE.read_text(encoding="utf-8")
    base = _base_stage(text)

    req_copy = base.index("COPY pyproject.toml requirements.txt")
    req_install = base.index("pip install --require-hashes -r requirements.txt")
    app_copy = base.index("COPY app ./app")
    local_install = base.index("pip install --no-deps .")

    assert req_copy < req_install < app_copy < local_install
    assert "OPS-28" in text
