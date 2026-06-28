# Stores application secrets in AWS Secrets Manager. ECS task definitions
# reference these by ARN and inject them as environment variables at runtime, so
# secret values never appear in task definitions or logs.
#
# We iterate over the non-sensitive `secret_names` (Terraform forbids using a
# sensitive value as a for_each key) and look up each value from the sensitive
# `secret_values` map only where it is consumed.

resource "aws_secretsmanager_secret" "this" {
  for_each = toset(var.secret_names)
  name     = "${var.name}/${each.key}"
  tags     = var.tags
}

resource "aws_secretsmanager_secret_version" "this" {
  for_each      = toset(var.secret_names)
  secret_id     = aws_secretsmanager_secret.this[each.key].id
  secret_string = var.secret_values[each.key]
}
