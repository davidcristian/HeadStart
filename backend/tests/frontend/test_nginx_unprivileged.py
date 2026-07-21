"""Regression: frontend nginx image runs unprivileged."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCKERFILE = _REPO_ROOT / "frontend" / "Dockerfile"
_NGINX_CONF = _REPO_ROOT / "frontend" / "nginx.conf"
_COMPOSE = _REPO_ROOT / "docker-compose.yml"
_ECS_MAIN = _REPO_ROOT / "devops" / "terraform" / "modules" / "ecs" / "main.tf"
_ALB_MAIN = _REPO_ROOT / "devops" / "terraform" / "modules" / "alb" / "main.tf"


def test_frontend_runtime_uses_unprivileged_nginx() -> None:
    """Runtime stage must not start stock nginx as root on privileged :80."""
    dockerfile = _DOCKERFILE.read_text(encoding="utf-8")
    assert "FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime" in dockerfile
    assert "FROM nginx:" not in dockerfile.split("AS runtime", 1)[-1]
    assert "EXPOSE 8080" in dockerfile
    assert "http://127.0.0.1:8080/" in dockerfile


def test_nginx_listens_on_unprivileged_port() -> None:
    """Conf must bind 8080 so the non-root master can accept connections."""
    conf = _NGINX_CONF.read_text(encoding="utf-8")
    assert "listen 8080;" in conf
    assert "listen 80;" not in conf


def test_compose_and_ecs_target_frontend_8080() -> None:
    """Local compose and ECS/ALB wiring must match the container listen port."""
    compose = _COMPOSE.read_text(encoding="utf-8")
    assert '"8080:8080"' in compose
    assert '"8080:80"' not in compose

    ecs = _ECS_MAIN.read_text(encoding="utf-8")
    assert "containerPort = 8080" in ecs
    assert "container_port   = 8080" in ecs

    alb = _ALB_MAIN.read_text(encoding="utf-8")
    # Target group port (task), not the public ALB listener on 80/443.
    assert "aws_lb_target_group" in alb and "frontend" in alb
    frontend_tg = alb.split('resource "aws_lb_target_group" "frontend"')[1].split(
        'resource "aws_lb_target_group"'
    )[0]
    assert "port        = 8080" in frontend_tg
