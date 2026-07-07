output "address" {
  value = (
    var.automatic_failover
    ? aws_elasticache_replication_group.this[0].primary_endpoint_address
    : aws_elasticache_cluster.this[0].cache_nodes[0].address
  )
}

output "port" {
  value = (
    var.automatic_failover
    ? aws_elasticache_replication_group.this[0].port
    : aws_elasticache_cluster.this[0].cache_nodes[0].port
  )
}
