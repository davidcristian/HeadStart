# All security groups in one place. Centralizing the inter-SG references avoids
# dependency cycles between the alb, ecs, rds, and redis modules.

resource "aws_security_group" "alb" {
  name        = "${var.name}-alb"
  description = "ALB ingress from the internet"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_security_group" "tasks" {
  name        = "${var.name}-tasks"
  description = "ECS task traffic"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_security_group" "rds" {
  name        = "${var.name}-rds"
  description = "Postgres access from ECS tasks"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_security_group" "redis" {
  name        = "${var.name}-redis"
  description = "Redis access from ECS tasks"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

# ---- ALB ----
resource "aws_security_group_rule" "alb_http_in" {
  type              = "ingress"
  security_group_id = aws_security_group.alb.id
  protocol          = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_blocks       = ["0.0.0.0/0"]
}

resource "aws_security_group_rule" "alb_https_in" {
  type              = "ingress"
  security_group_id = aws_security_group.alb.id
  protocol          = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_blocks       = ["0.0.0.0/0"]
}

resource "aws_security_group_rule" "alb_egress" {
  type              = "egress"
  security_group_id = aws_security_group.alb.id
  protocol          = "-1"
  from_port         = 0
  to_port           = 0
  cidr_blocks       = ["0.0.0.0/0"]
}

# ---- Tasks ----
# Only the ALB target-group ports (frontend 8080, api 8000). A 0 to 65535
# range would also expose the worker metrics port (9090) to the ALB SG.
# The SPA container listens on unprivileged :8080, not privileged :80.
resource "aws_security_group_rule" "tasks_http_from_alb" {
  type                     = "ingress"
  security_group_id        = aws_security_group.tasks.id
  protocol                 = "tcp"
  from_port                = 8080
  to_port                  = 8080
  source_security_group_id = aws_security_group.alb.id
}

resource "aws_security_group_rule" "tasks_api_from_alb" {
  type                     = "ingress"
  security_group_id        = aws_security_group.tasks.id
  protocol                 = "tcp"
  from_port                = 8000
  to_port                  = 8000
  source_security_group_id = aws_security_group.alb.id
}

resource "aws_security_group_rule" "tasks_egress" {
  type              = "egress"
  security_group_id = aws_security_group.tasks.id
  protocol          = "-1"
  from_port         = 0
  to_port           = 0
  cidr_blocks       = ["0.0.0.0/0"]
}

# ---- RDS ----
resource "aws_security_group_rule" "rds_from_tasks" {
  type                     = "ingress"
  security_group_id        = aws_security_group.rds.id
  protocol                 = "tcp"
  from_port                = 5432
  to_port                  = 5432
  source_security_group_id = aws_security_group.tasks.id
}

# ---- Redis ----
resource "aws_security_group_rule" "redis_from_tasks" {
  type                     = "ingress"
  security_group_id        = aws_security_group.redis.id
  protocol                 = "tcp"
  from_port                = 6379
  to_port                  = 6379
  source_security_group_id = aws_security_group.tasks.id
}
