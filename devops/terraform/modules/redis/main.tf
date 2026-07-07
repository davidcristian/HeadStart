# ElastiCache Redis used as the Celery broker + result backend.
# Single-node cluster by default (beta/cheap); replication group with
# automatic failover when automatic_failover is true (prod).

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name}-redis"
  subnet_ids = var.subnet_ids
  tags       = var.tags
}

resource "aws_elasticache_cluster" "this" {
  count = var.automatic_failover ? 0 : 1

  cluster_id           = "${var.name}-redis"
  engine               = "redis"
  engine_version       = var.engine_version
  node_type            = var.node_type
  num_cache_nodes      = 1
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.this.name
  security_group_ids   = [var.security_group_id]
  parameter_group_name = var.parameter_group_name
  tags                 = var.tags
}

resource "aws_elasticache_replication_group" "this" {
  count = var.automatic_failover ? 1 : 0

  replication_group_id = "${var.name}-redis"
  description          = "${var.name} Celery broker (HA)"
  engine               = "redis"
  engine_version       = var.engine_version
  node_type            = var.node_type
  num_cache_clusters   = var.num_cache_clusters
  port                 = 6379
  parameter_group_name = var.parameter_group_name
  subnet_group_name    = aws_elasticache_subnet_group.this.name
  security_group_ids   = [var.security_group_id]

  automatic_failover_enabled = true
  multi_az_enabled           = true

  tags = var.tags
}
