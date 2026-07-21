# ElastiCache Redis used as the Celery broker + result backend.
# Always a replication group so transit encryption + AUTH are available.
# Single-node cache clusters cannot enable in-transit encryption.
# automatic_failover selects Multi-AZ HA (prod) vs a single primary (beta).

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name}-redis"
  subnet_ids = var.subnet_ids
  tags       = var.tags
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = "${var.name}-redis"
  description          = "${var.name} Celery broker"
  engine               = "redis"
  engine_version       = var.engine_version
  node_type            = var.node_type
  num_cache_clusters   = var.automatic_failover ? max(var.num_cache_clusters, 2) : var.num_cache_clusters
  port                 = 6379
  parameter_group_name = var.parameter_group_name
  subnet_group_name    = aws_elasticache_subnet_group.this.name
  security_group_ids   = [var.security_group_id]

  automatic_failover_enabled = var.automatic_failover
  multi_az_enabled           = var.automatic_failover

  # Encrypt broker traffic and snapshots; require AUTH over TLS.
  transit_encryption_enabled = true
  at_rest_encryption_enabled = true
  auth_token                 = var.auth_token
  kms_key_id                 = var.kms_key_id == "" ? null : var.kms_key_id

  tags = var.tags
}
