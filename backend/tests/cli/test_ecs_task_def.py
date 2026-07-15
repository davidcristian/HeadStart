"""Unit tests for ECS task-definition image retargeting (OPS-01)."""

from __future__ import annotations

import json
import runpy
from io import StringIO
from typing import Any

import pytest

from app.cli.ecs_task_def import (
    image_repo_for_family,
    image_uri,
    main,
    normalize_image_digest,
    retarget_task_definition,
)


def _sample_task_def(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "taskDefinitionArn": "arn:aws:ecs:us-east-2:123:task-definition/headstart-api:9",
        "family": "headstart-api",
        "revision": 9,
        "status": "ACTIVE",
        "requiresCompatibilities": ["FARGATE"],
        "networkMode": "awsvpc",
        "cpu": "256",
        "memory": "512",
        "executionRoleArn": "arn:aws:iam::123:role/exec",
        "taskRoleArn": "arn:aws:iam::123:role/task",
        "containerDefinitions": [
            {
                "name": "api",
                "image": "123.dkr.ecr.us-east-2.amazonaws.com/headstart-backend:latest",
                "essential": True,
                "environment": [{"name": "APP_ENV", "value": "beta"}],
            }
        ],
        "requiresAttributes": [{"name": "ecs.capability.execution-role-ecr-pull"}],
        "compatibilities": ["FARGATE"],
        "registeredAt": "2026-07-01T00:00:00.000000+00:00",
        "registeredBy": "arn:aws:iam::123:user/ci",
    }
    base.update(overrides)
    return base


def test_image_repo_for_known_families() -> None:
    assert image_repo_for_family("headstart-api") == "headstart-backend"
    assert image_repo_for_family("headstart-worker") == "headstart-backend-worker"
    assert image_repo_for_family("headstart-frontend") == "headstart-frontend"
    assert image_repo_for_family("headstart-migrate") == "headstart-backend"
    assert image_repo_for_family("headstart-beat") == "headstart-backend"


def test_image_repo_rejects_unknown_family() -> None:
    with pytest.raises(ValueError, match="unknown task family"):
        image_repo_for_family("headstart-unknown")


def test_image_uri_strips_trailing_slash() -> None:
    assert (
        image_uri("123.dkr.ecr.us-east-2.amazonaws.com/", "headstart-api", "abc1234")
        == "123.dkr.ecr.us-east-2.amazonaws.com/headstart-backend:abc1234"
    )


def test_image_uri_appends_sha256_digest() -> None:
    """OPS-64: tag@digest pins the exact ECR manifest, not only the tag."""
    digest = "sha256:" + ("ab" * 32)
    assert (
        image_uri(
            "123.dkr.ecr.us-east-2.amazonaws.com",
            "headstart-worker",
            "deadbeef",
            digest=digest,
        )
        == f"123.dkr.ecr.us-east-2.amazonaws.com/headstart-backend-worker:deadbeef@{digest}"
    )


def test_normalize_image_digest_rejects_non_sha256() -> None:
    with pytest.raises(ValueError, match="sha256:"):
        normalize_image_digest("md5:abc")
    with pytest.raises(ValueError, match="empty"):
        normalize_image_digest("sha256:")


def test_retarget_replaces_image_and_strips_read_only_fields() -> None:
    rewritten = retarget_task_definition(
        _sample_task_def(),
        image="123.dkr.ecr.us-east-2.amazonaws.com/headstart-backend:deadbeef",
    )
    assert rewritten["family"] == "headstart-api"
    assert rewritten["cpu"] == "256"
    assert rewritten["containerDefinitions"][0]["image"].endswith(":deadbeef")
    assert rewritten["containerDefinitions"][0]["environment"] == [
        {"name": "APP_ENV", "value": "beta"}
    ]
    for key in (
        "taskDefinitionArn",
        "revision",
        "status",
        "requiresAttributes",
        "compatibilities",
        "registeredAt",
        "registeredBy",
    ):
        assert key not in rewritten


def test_retarget_updates_every_container() -> None:
    task = _sample_task_def(
        containerDefinitions=[
            {"name": "a", "image": "old:1"},
            {"name": "b", "image": "old:2"},
        ]
    )
    rewritten = retarget_task_definition(task, image="reg/repo:new")
    assert [c["image"] for c in rewritten["containerDefinitions"]] == [
        "reg/repo:new",
        "reg/repo:new",
    ]


def test_retarget_rejects_empty_image() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        retarget_task_definition(_sample_task_def(), image="  ")


def test_retarget_rejects_missing_containers() -> None:
    with pytest.raises(ValueError, match="containerDefinitions"):
        retarget_task_definition(_sample_task_def(containerDefinitions=[]), image="x:y")


def test_retarget_rejects_non_object_container() -> None:
    with pytest.raises(ValueError, match="objects"):
        retarget_task_definition(
            _sample_task_def(containerDefinitions=["bad"]),
            image="x:y",
        )


def test_main_retarget_from_describe_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    envelope = {"taskDefinition": _sample_task_def()}
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(envelope)))
    out = StringIO()
    monkeypatch.setattr("sys.stdout", out)
    assert (
        main(
            [
                "retarget",
                "--ecr-registry",
                "123.dkr.ecr.us-east-2.amazonaws.com",
                "--family",
                "headstart-api",
                "--image-tag",
                "abc1234",
            ]
        )
        == 0
    )
    payload = json.loads(out.getvalue())
    assert (
        payload["containerDefinitions"][0]["image"]
        == "123.dkr.ecr.us-east-2.amazonaws.com/headstart-backend:abc1234"
    )
    assert "revision" not in payload


def test_main_retarget_with_image_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    digest = "sha256:" + ("cd" * 32)
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(_sample_task_def())))
    out = StringIO()
    monkeypatch.setattr("sys.stdout", out)
    assert (
        main(
            [
                "retarget",
                "--ecr-registry",
                "123.dkr.ecr.us-east-2.amazonaws.com",
                "--family",
                "headstart-frontend",
                "--image-tag",
                "abc1234",
                "--image-digest",
                digest,
            ]
        )
        == 0
    )
    payload = json.loads(out.getvalue())
    assert (
        payload["containerDefinitions"][0]["image"]
        == f"123.dkr.ecr.us-east-2.amazonaws.com/headstart-frontend:abc1234@{digest}"
    )


def test_main_rejects_digest_with_explicit_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(_sample_task_def())))
    with pytest.raises(SystemExit, match="cannot be combined"):
        main(
            [
                "retarget",
                "--image",
                "reg/headstart-backend:sha",
                "--image-digest",
                "sha256:abc",
            ]
        )


def test_main_rejects_invalid_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(_sample_task_def())))
    with pytest.raises(SystemExit, match="sha256:"):
        main(
            [
                "retarget",
                "--ecr-registry",
                "123.dkr.ecr.us-east-2.amazonaws.com",
                "--family",
                "headstart-api",
                "--image-tag",
                "abc1234",
                "--image-digest",
                "not-a-digest",
            ]
        )


def test_main_retarget_with_explicit_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(_sample_task_def())))
    out = StringIO()
    monkeypatch.setattr("sys.stdout", out)
    assert main(["retarget", "--image", "reg/headstart-backend:sha"]) == 0
    payload = json.loads(out.getvalue())
    assert payload["containerDefinitions"][0]["image"] == "reg/headstart-backend:sha"


def test_main_requires_image_or_family_args(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    with pytest.raises(SystemExit, match="requires --image"):
        main(["retarget"])


def test_main_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", StringIO("not-json"))
    with pytest.raises(SystemExit, match="invalid JSON"):
        main(["retarget", "--image", "x:y"])


def test_main_rejects_non_object_task_def(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", StringIO("[]"))
    with pytest.raises(SystemExit, match="taskDefinition object"):
        main(["retarget", "--image", "x:y"])


def test_main_surfaces_retarget_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.stdin",
        StringIO(json.dumps({"family": "headstart-api", "containerDefinitions": []})),
    )
    with pytest.raises(SystemExit, match="containerDefinitions"):
        main(["retarget", "--image", "x:y"])


def test_main_rejects_envelope_with_non_object_task_def(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps({"taskDefinition": []})))
    with pytest.raises(SystemExit, match="taskDefinition object"):
        main(["retarget", "--image", "x:y"])


def test_module_entrypoint_invokes_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """``python -m app.cli.ecs_task_def`` exits via ``main()``."""
    monkeypatch.setattr(
        "sys.argv",
        ["ecs_task_def", "retarget", "--image", "reg/headstart-backend:sha"],
    )
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(_sample_task_def())))
    out = StringIO()
    monkeypatch.setattr("sys.stdout", out)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("app.cli.ecs_task_def", run_name="__main__")
    assert exc.value.code == 0
    payload = json.loads(out.getvalue())
    assert payload["containerDefinitions"][0]["image"] == "reg/headstart-backend:sha"
