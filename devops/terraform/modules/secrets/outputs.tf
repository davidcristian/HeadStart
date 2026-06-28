output "secret_arns" {
  description = "Map of secret key -> Secrets Manager ARN (use in ECS `secrets`)."
  value       = { for k, s in aws_secretsmanager_secret.this : k => s.arn }
}
