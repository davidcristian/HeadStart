"""Regression: deploy pins ECS images to ECR content digests (OPS-64)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEPLOY_SH = _REPO_ROOT / "scripts" / "deploy.sh"


def test_deploy_resolves_ecr_digests_before_retarget() -> None:
    """Tag-only retarget leaves a provenance gap; digest pin must precede rolls."""
    text = _DEPLOY_SH.read_text(encoding="utf-8")
    assert "ecr_image_digest" in text
    assert "aws ecr describe-images" in text
    assert "imageDetails[0].imageDigest" in text
    assert "--image-digest" in text
    assert "DIGEST_BACKEND" in text
    assert "DIGEST_WORKER" in text
    assert "DIGEST_FRONTEND" in text
    digest_pos = text.index('DIGEST_BACKEND="$(ecr_image_digest')
    retarget_pos = text.index("register_retargeted_task_def")
    # First call site after the helper defs is the migrate registration.
    migrate_call = text.index(
        'migrate_td="$(register_retargeted_task_def',
        retarget_pos,
    )
    assert digest_pos < migrate_call, "ECR digests must resolve before task-def retarget"


def test_deploy_digest_helper_requires_sha256() -> None:
    """Non-digest ECR responses must abort rather than register a tag-only pin."""
    text = _DEPLOY_SH.read_text(encoding="utf-8")
    start = text.index("ecr_image_digest()")
    end = text.index("\ndigest_for_family()", start)
    helper = text[start:end]
    assert "sha256:*" in helper
    assert 'die "ECR returned no sha256 digest' in helper
