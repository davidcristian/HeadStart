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

output "access_logs_bucket" {
  description = "S3 bucket receiving ALB access logs."
  value       = aws_s3_bucket.access_logs.id
}

output "web_acl_arn" {
  description = "WAFv2 web ACL ARN associated with the ALB."
  value       = aws_wafv2_web_acl.this.arn
}
