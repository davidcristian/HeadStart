output "dns_name" {
  value = aws_lb.this.dns_name
}

output "zone_id" {
  description = "Route53 hosted zone ID for the ALB (for alias records)."
  value       = aws_lb.this.zone_id
}

output "frontend_target_group_arn" {
  value = aws_lb_target_group.frontend.arn
}

output "api_target_group_arn" {
  value = aws_lb_target_group.api.arn
}

output "http_listener_arn" {
  value = aws_lb_listener.http.arn
}

output "https_listener_arn" {
  value = try(aws_lb_listener.https[0].arn, null)
}

output "https_enabled" {
  value = local.https_enabled
}
