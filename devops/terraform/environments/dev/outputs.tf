output "alb_dns_name" {
  value = module.stack.alb_dns_name
}

output "ecs_cluster_name" {
  value = module.stack.ecs_cluster_name
}

output "ecr_repository_urls" {
  value = module.stack.ecr_repository_urls
}
