# Stores application secrets in AWS Secrets Manager. ECS task definitions
# reference these by ARN and inject them as environment variables at runtime, so
# secret values never appear in task definitions or logs.
#
# We iterate over the non-sensitive `secret_names` (Terraform forbids using a
# sensitive value as a for_each key) and look up each value from the sensitive
# `secret_values` map only where it is consumed.
#
# Secrets are encrypted with a customer-managed KMS key and keep an
# explicit recovery window so deletes cannot silently use an undocumented
# default.

resource "aws_secretsmanager_secret" "this" {
  for_each                = toset(var.secret_names)
  name                    = "${var.name}/${each.key}"
  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = var.recovery_window_in_days
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "this" {
  for_each      = toset(var.secret_names)
  secret_id     = aws_secretsmanager_secret.this[each.key].id
  secret_string = var.secret_values[each.key]
}
