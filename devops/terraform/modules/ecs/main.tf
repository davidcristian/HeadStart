# ECS Fargate cluster running four services from two images:
#   api, worker, beat  -> backend image (role chosen via container command)
#   frontend           -> frontend image
# Plus a one-off `migrate` task definition invoked by scripts/deploy.sh.

locals {
  backend_ref        = "${var.backend_image}:${var.image_tag}"
  worker_backend_ref = "${var.worker_backend_image}:${var.image_tag}"
  frontend_ref       = "${var.frontend_image}:${var.image_tag}"

  env_list     = [for k, v in var.environment : { name = k, value = v }]
  secrets_list = [for k, v in var.secrets : { name = k, valueFrom = v }]

  log_config = {
    logDriver = "awslogs"
    options = {
      "awslogs-group"         = aws_cloudwatch_log_group.this.name
      "awslogs-region"        = var.region
      "awslogs-stream-prefix" = "jobnotifier"
    }
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
  backend_container = { for role in ["api", "beat", "migrate"] :
    role => jsonencode([{
      name             = role
      image            = local.backend_ref
      command          = [role]
      essential        = true
      portMappings     = role == "api" ? [{ containerPort = 8000, protocol = "tcp" }] : []
      environment      = local.env_list
      secrets          = local.secrets_list
      logConfiguration = local.log_config
    }])
  }
  worker_container = jsonencode([{
    name             = "worker"
    image            = local.worker_backend_ref
    command          = ["worker"]
    essential        = true
    portMappings     = [{ containerPort = 9090, protocol = "tcp" }]
    environment      = local.env_list
    secrets          = local.secrets_list
    logConfiguration = local.log_config
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
    name             = "frontend"
    image            = local.frontend_ref
    essential        = true
    portMappings     = [{ containerPort = 80, protocol = "tcp" }]
    logConfiguration = local.log_config
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
    container_port   = 80
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
