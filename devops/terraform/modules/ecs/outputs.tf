output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "cluster_arn" {
  value = aws_ecs_cluster.this.arn
}

output "service_names" {
  value = {
    api      = aws_ecs_service.api.name
    frontend = aws_ecs_service.frontend.name
    worker   = aws_ecs_service.worker.name
    beat     = aws_ecs_service.beat.name
  }
}
