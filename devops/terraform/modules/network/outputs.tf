output "vpc_id" {
  value = aws_vpc.this.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "flow_log_group_name" {
  description = "CloudWatch log group receiving VPC flow logs (OPS-41)."
  value       = aws_cloudwatch_log_group.flow_log.name
}
