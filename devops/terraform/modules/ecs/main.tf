# ECS Fargate cluster running four services from two images:
#   api, worker, beat  -> backend image (role chosen via container command)
#   frontend           -> frontend image
# Plus a one-off `migrate` task definition invoked by scripts/deploy.sh.
#
# Every long-running container runs non-root, with a read-only root filesystem
# (+ /tmp tmpfs), container healthCheck, and CapabilityBoundingSet drop-all.
# Worker keeps RuntimeDefault seccomp around Chromium.

locals {
  backend_ref        = "${var.backend_image}:${var.image_tag}"
  worker_backend_ref = "${var.worker_backend_image}:${var.image_tag}"
  frontend_ref       = "${var.frontend_image}:${var.image_tag}"

  env_list     = [for k, v in var.environment : { name = k, value = v }]
  secrets_list = [for k, v in var.secrets : { name = k, valueFrom = v }]

  # Images already USER appuser (uid 10001) / nginx (uid 101); pin in the task
  # def so a rebuilt image cannot silently revert to root.
  backend_user  = "10001:10001"
  frontend_user = "101:101"

  log_config = {
    logDriver = "awslogs"
    options = {
      "awslogs-group"         = aws_cloudwatch_log_group.this.name
      "awslogs-region"        = var.region
      "awslogs-stream-prefix" = "headstart"
    }
  }

  # Scratch for Celery beat schedule, Playwright/Chromium, uvicorn, nginx temps.
  tmp_tmpfs = {
    containerPath = "/tmp"
    size          = 256
    mountOptions  = ["rw", "nosuid", "nodev", "noexec"]
  }
  worker_tmp_tmpfs = {
    containerPath = "/tmp"
    size          = 512
    mountOptions  = ["rw", "nosuid", "nodev", "noexec"]
  }
  frontend_tmpfs = [
    {
      containerPath = "/tmp"
      size          = 64
      mountOptions  = ["rw", "nosuid", "nodev", "noexec"]
    },
    {
      containerPath = "/var/cache/nginx"
      size          = 64
      mountOptions  = ["rw", "nosuid", "nodev", "noexec"]
    },
    {
      containerPath = "/var/run"
      size          = 16
      mountOptions  = ["rw", "nosuid", "nodev", "noexec"]
    },
  ]

  # Shared linux hardening; worker adds larger /tmp for Chromium scratch.
  base_linux_parameters = {
    initProcessEnabled = true
    capabilities = {
      drop = ["ALL"]
    }
    seccompProfile = {
      type = "RuntimeDefault"
    }
  }

  api_health_check = {
    command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)\""]
    interval    = 30
    timeout     = 5
    retries     = 3
    startPeriod = 60
  }
  # METRICS_TOKEN is always set on AWS; 401 still proves the scrape port is up.
  worker_health_check = {
    command = [
      "CMD-SHELL",
      "python -c \"import urllib.error,urllib.request\\ntry:\\n urllib.request.urlopen('http://127.0.0.1:9090/metrics', timeout=2)\\nexcept urllib.error.HTTPError as e:\\n assert e.code in (401, 403)\"",
    ]
    interval    = 30
    timeout     = 5
    retries     = 3
    startPeriod = 90
  }
  beat_health_check = {
    command = [
      "CMD-SHELL",
      "python -c \"from pathlib import Path; assert any(b'beat' in Path(f'/proc/{p.name}/cmdline').read_bytes() for p in Path('/proc').iterdir() if p.name.isdigit())\"",
    ]
    interval    = 30
    timeout     = 5
    retries     = 3
    startPeriod = 60
  }
  frontend_health_check = {
    command     = ["CMD-SHELL", "wget -qO /dev/null http://127.0.0.1:8080/ || exit 1"]
    interval    = 30
    timeout     = 5
    retries     = 3
    startPeriod = 30
  }
}

resource "aws_ecs_cluster" "this" {
  name = var.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = var.tags
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

# Helper to build a backend container definition for a given role/command.
locals {
  backend_health_by_role = {
    api  = local.api_health_check
    beat = local.beat_health_check
  }
  backend_container_objects = { for role in ["api", "beat", "migrate"] :
    role => merge(
      {
        name                   = role
        image                  = local.backend_ref
        command                = [role]
        essential              = true
        user                   = local.backend_user
        readonlyRootFilesystem = true
        portMappings           = role == "api" ? [{ containerPort = 8000, protocol = "tcp" }] : []
        environment            = local.env_list
        secrets                = local.secrets_list
        logConfiguration       = local.log_config
        linuxParameters = merge(local.base_linux_parameters, {
          tmpfs = [local.tmp_tmpfs]
        })
      },
      # One-off migrate has no long-lived probe; api/beat get healthCheck.
      contains(keys(local.backend_health_by_role), role) ? {
        healthCheck = local.backend_health_by_role[role]
      } : {},
    )
  }
  backend_container = {
    for role, obj in local.backend_container_objects : role => jsonencode([obj])
  }
  # Seccomp + readonly/non-root/healthCheck around Chromium scrapes.
  worker_container = jsonencode([{
    name                   = "worker"
    image                  = local.worker_backend_ref
    command                = ["worker"]
    essential              = true
    user                   = local.backend_user
    readonlyRootFilesystem = true
    portMappings           = [{ containerPort = 9090, protocol = "tcp" }]
    environment            = local.env_list
    secrets                = local.secrets_list
    logConfiguration       = local.log_config
    healthCheck            = local.worker_health_check
    linuxParameters = merge(local.base_linux_parameters, {
      tmpfs = [local.worker_tmp_tmpfs]
    })
  }])
}

# ---- Task definitions ----
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.service_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  container_definitions    = local.backend_container["api"]
  tags                     = var.tags
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.service_prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  container_definitions    = local.worker_container
  tags                     = var.tags
}

resource "aws_ecs_task_definition" "beat" {
  family                   = "${var.service_prefix}-beat"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  container_definitions    = local.backend_container["beat"]
  tags                     = var.tags
}

resource "aws_ecs_task_definition" "migrate" {
  family                   = "${var.service_prefix}-migrate"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  container_definitions    = local.backend_container["migrate"]
  tags                     = var.tags
}

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.service_prefix}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  container_definitions = jsonencode([{
    name                   = "frontend"
    image                  = local.frontend_ref
    essential              = true
    user                   = local.frontend_user
    readonlyRootFilesystem = true
    portMappings           = [{ containerPort = 8080, protocol = "tcp" }]
    logConfiguration       = local.log_config
    healthCheck            = local.frontend_health_check
    linuxParameters = merge(local.base_linux_parameters, {
      tmpfs = local.frontend_tmpfs
    })
  }])
  tags = var.tags
}

# ---- Services ----
resource "aws_ecs_service" "api" {
  name            = "${var.service_prefix}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.desired_counts.api
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [var.tasks_security_group_id]
  }

  load_balancer {
    target_group_arn = var.api_target_group_arn
    container_name   = "api"
    container_port   = 8000
  }

  lifecycle {
    ignore_changes = [task_definition] # deploy.sh rolls new task defs
  }

  tags = var.tags
}

resource "aws_ecs_service" "frontend" {
  name            = "${var.service_prefix}-frontend"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = var.desired_counts.frontend
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [var.tasks_security_group_id]
  }

  load_balancer {
    target_group_arn = var.frontend_target_group_arn
    container_name   = "frontend"
    container_port   = 8080
  }

  lifecycle {
    ignore_changes = [task_definition]
  }

  tags = var.tags
}

resource "aws_ecs_service" "worker" {
  name            = "${var.service_prefix}-worker"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.desired_counts.worker
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [var.tasks_security_group_id]
  }

  lifecycle {
    ignore_changes = [task_definition]
  }

  tags = var.tags
}

resource "aws_ecs_service" "beat" {
  name            = "${var.service_prefix}-beat"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.beat.arn
  desired_count   = var.desired_counts.beat
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [var.tasks_security_group_id]
  }

  lifecycle {
    ignore_changes = [task_definition]
  }

  tags = var.tags
}
