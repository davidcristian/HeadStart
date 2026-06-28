output "dns_name" {
  value = aws_lb.this.dns_name
}

output "frontend_target_group_arn" {
  value = aws_lb_target_group.frontend.arn
}

output "api_target_group_arn" {
  value = aws_lb_target_group.api.arn
}

output "listener_arn" {
  value = aws_lb_listener.http.arn
}
