"""Regression: tasks SG ingress from ALB is limited to target ports (OPS-14)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SECURITY_MAIN = _REPO_ROOT / "devops" / "terraform" / "modules" / "security" / "main.tf"


def test_tasks_ingress_from_alb_is_limited_to_target_ports() -> None:
    """ALB may reach frontend :80 and api :8000 only — not 0–65535 / metrics :9090."""
    main = _SECURITY_MAIN.read_text(encoding="utf-8")
    assert 'resource "aws_security_group_rule" "tasks_from_alb"' not in main
    assert "to_port                  = 65535" not in main
    assert 'resource "aws_security_group_rule" "tasks_http_from_alb"' in main
    assert 'resource "aws_security_group_rule" "tasks_api_from_alb"' in main

    alb_sourced: list[tuple[int, int]] = []
    for match in re.finditer(
        r'resource\s+"aws_security_group_rule"\s+"[^"]+"\s*\{([^}]+)\}',
        main,
        flags=re.DOTALL,
    ):
        body = match.group(1)
        if "source_security_group_id = aws_security_group.alb.id" not in body:
            continue
        if "security_group_id        = aws_security_group.tasks.id" not in body:
            continue
        from_m = re.search(r"from_port\s+=\s+(\d+)", body)
        to_m = re.search(r"to_port\s+=\s+(\d+)", body)
        assert from_m is not None and to_m is not None, body
        alb_sourced.append((int(from_m.group(1)), int(to_m.group(1))))

    assert sorted(alb_sourced) == [(80, 80), (8000, 8000)]
    assert not any(lo <= 9090 <= hi for lo, hi in alb_sourced)
