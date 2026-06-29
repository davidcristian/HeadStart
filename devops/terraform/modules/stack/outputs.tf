output "alb_dns_name" {
  description = "Public DNS name of the load balancer."
  value       = module.alb.dns_name
}

output "app_url" {
  description = "Primary URL for the app (HTTPS custom domain when configured, else HTTP ALB DNS)."
  value       = local.app_base_url
}

output "https_enabled" {
  description = "Whether the ALB terminates TLS on port 443."
  value       = module.alb.https_enabled
}

output "domain_name" {
  description = "Custom hostname when configured."
  value       = var.domain_name != "" ? var.domain_name : null
}

output "ecs_cluster_name" {
  value = module.ecs.cluster_name
}

output "ecr_repository_urls" {
  value = module.ecr.repository_urls
}

output "rds_address" {
  value = module.rds.address
}

output "redis_address" {
  value = module.redis.address
}
