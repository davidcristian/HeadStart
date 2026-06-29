output "region" {
  value = var.region
}

output "alb_dns_name" {
  value = module.stack.alb_dns_name
}

output "app_url" {
  description = "Primary URL for the app (HTTPS when a custom domain is configured)."
  value       = module.stack.app_url
}

output "https_enabled" {
  value = module.stack.https_enabled
}

output "ecs_cluster_name" {
  value = module.stack.ecs_cluster_name
}

output "ecr_repository_urls" {
  value = module.stack.ecr_repository_urls
}
