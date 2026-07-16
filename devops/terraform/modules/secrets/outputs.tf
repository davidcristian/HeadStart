output "secret_arns" {
  description = "Map of secret key -> Secrets Manager ARN (use in ECS `secrets`)."
  value       = { for k, s in aws_secretsmanager_secret.this : k => s.arn }
}

output "kms_key_arn" {
  description = "CMK ARN used to encrypt Secrets Manager secrets (grant kms:Decrypt to readers)."
  value       = aws_kms_key.secrets.arn
}
