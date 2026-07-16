"""Regression: compose must not float local or ntfy images on :latest (OPS-56)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE = _REPO_ROOT / "docker-compose.yml"
_DEPLOYMENT_DOC = _REPO_ROOT / "docs" / "modules" / "deployment.md"

_IMAGE_LINE = re.compile(r"(?m)^\s*image:\s*(\S+)\s*$")
_LOCAL_IMAGES = {
    "headstart/backend:local",
    "headstart/backend-worker:local",
    "headstart/frontend:local",
}
_NTFY_PIN = re.compile(r"^binwiederhier/ntfy:v\d+\.\d+\.\d+@sha256:[0-9a-f]{64}$")


def _compose_images() -> list[str]:
    """Return every ``image:`` reference from the root compose file."""
    text = _COMPOSE.read_text(encoding="utf-8")
    return _IMAGE_LINE.findall(text)


def test_compose_has_no_latest_image_tags() -> None:
    """No service may reference a mutable ``:latest`` tag (OPS-56)."""
    latest = [img for img in _compose_images() if img.endswith(":latest")]
    assert latest == [], f"compose still floats :latest: {latest}"


def test_local_app_images_use_local_tag() -> None:
    """Compose-built app images use the fixed ``:local`` build tag."""
    images = set(_compose_images())
    missing = _LOCAL_IMAGES - images
    assert missing == set(), f"missing local image pins: {missing}"
    for img in images:
        if img.startswith("headstart/"):
            assert img.endswith(":local"), f"headstart image not :local: {img}"


def test_ntfy_is_version_and_digest_pinned() -> None:
    """Offline-profile ntfy must pin a concrete version and index digest."""
    ntfy = [img for img in _compose_images() if img.startswith("binwiederhier/ntfy")]
    assert len(ntfy) == 1, f"expected one ntfy image, got {ntfy}"
    assert _NTFY_PIN.match(ntfy[0]), f"ntfy not version+digest pinned: {ntfy[0]}"


def test_deployment_doc_covers_compose_image_pins() -> None:
    """deployment.md must document the compose pin contract (OPS-56)."""
    text = _DEPLOYMENT_DOC.read_text(encoding="utf-8")
    assert "OPS-56" in text
    assert "headstart/backend:local" in text
    assert "binwiederhier/ntfy:v" in text
