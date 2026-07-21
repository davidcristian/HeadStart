output "address" {
  value = aws_db_instance.this.address
}

output "port" {
  value = aws_db_instance.this.port
}

output "db_name" {
  value = aws_db_instance.this.db_name
}

output "kms_key_arn" {
  value       = aws_kms_key.rds.arn
  description = "CMK used for RDS storage and Performance Insights."
}

output "monitoring_role_arn" {
  value       = aws_iam_role.monitoring.arn
  description = "IAM role ARN for RDS Enhanced Monitoring."
}
