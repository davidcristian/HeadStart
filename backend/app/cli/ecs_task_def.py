"""Rewrite an ECS task-definition JSON so containers pin a freshly pushed image.

``scripts/deploy.sh`` describes the current family revision, pipes it through
this helper to swap the image tag, then registers the result. That keeps env,
secrets, and CPU/memory from Terraform while ensuring the rolled revision
points at the SHA just pushed to ECR (OPS-01).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

# Fields returned by DescribeTaskDefinition that RegisterTaskDefinition rejects.
_READ_ONLY_KEYS = frozenset(
    {
        "taskDefinitionArn",
        "revision",
        "status",
        "requiresAttributes",
        "compatibilities",
        "registeredAt",
        "registeredBy",
        "deregisteredAt",
    }
)

# Stable family suffix -> ECR repository name (matches stack/ecr wiring).
_FAMILY_IMAGE_REPOS: dict[str, str] = {
    "api": "headstart-backend",
    "beat": "headstart-backend",
    "migrate": "headstart-backend",
    "worker": "headstart-backend-worker",
    "frontend": "headstart-frontend",
}


def image_repo_for_family(family: str) -> str:
    """Map a task family (``headstart-api``) to its ECR repository name."""
    suffix = family.rsplit("-", 1)[-1]
    try:
        return _FAMILY_IMAGE_REPOS[suffix]
    except KeyError as exc:
        raise ValueError(f"unknown task family for image retarget: {family!r}") from exc


def image_uri(ecr_registry: str, family: str, image_tag: str) -> str:
    """Build ``{registry}/{repo}:{tag}`` for a known task family."""
    registry = ecr_registry.rstrip("/")
    return f"{registry}/{image_repo_for_family(family)}:{image_tag}"


def retarget_task_definition(
    task_definition: dict[str, Any],
    *,
    image: str,
) -> dict[str, Any]:
    """Return a RegisterTaskDefinition payload with every container on ``image``.

    Preserves non-image fields from the described revision so deploy rolls only
    the image pin, not Terraform-managed env/secrets/sizing.
    """
    if not image.strip():
        raise ValueError("image must be a non-empty container image URI")

    containers = task_definition.get("containerDefinitions")
    if not isinstance(containers, list) or not containers:
        raise ValueError("task definition has no containerDefinitions")

    rewritten = dict(task_definition)
    for key in _READ_ONLY_KEYS:
        rewritten.pop(key, None)

    new_containers: list[dict[str, Any]] = []
    for container in containers:
        if not isinstance(container, dict):
            raise ValueError("containerDefinitions entries must be objects")
        updated = dict(container)
        updated["image"] = image
        new_containers.append(updated)
    rewritten["containerDefinitions"] = new_containers
    return rewritten


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Retarget ECS task-definition JSON images for deploy.sh.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    retarget = sub.add_parser(
        "retarget",
        help="Rewrite stdin taskDefinition JSON to pin --image (or family+tag).",
    )
    retarget.add_argument(
        "--image",
        default="",
        help="Full container image URI to set on every container.",
    )
    retarget.add_argument(
        "--ecr-registry",
        default="",
        help="ECR registry host; used with --family and --image-tag.",
    )
    retarget.add_argument(
        "--family",
        default="",
        help="Task family (e.g. headstart-api); used with --ecr-registry/--image-tag.",
    )
    retarget.add_argument(
        "--image-tag",
        default="",
        help="Image tag (usually git SHA); used with --ecr-registry/--family.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry: read DescribeTaskDefinition JSON on stdin, print register JSON."""
    args = _build_parser().parse_args(argv)
    # Subparsers are required; only ``retarget`` is registered today.
    assert args.command == "retarget"

    image = args.image.strip()
    if not image:
        if not (args.ecr_registry and args.family and args.image_tag):
            raise SystemExit(
                "retarget requires --image, or --ecr-registry + --family + --image-tag"
            )
        image = image_uri(args.ecr_registry, args.family, args.image_tag)

    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON on stdin: {exc}") from exc

    # Accept either the bare taskDefinition object or a describe-task-definition
    # envelope so callers can pipe aws CLI output without --query.
    if isinstance(payload, dict) and "taskDefinition" in payload:
        task_definition = payload["taskDefinition"]
    else:
        task_definition = payload
    if not isinstance(task_definition, dict):
        raise SystemExit("stdin must be a taskDefinition object or describe envelope")

    try:
        rewritten = retarget_task_definition(task_definition, image=image)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    json.dump(rewritten, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
