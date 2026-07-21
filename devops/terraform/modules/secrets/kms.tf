# Customer-managed KMS key for Secrets Manager.
# Isolates JWT / Fernet / DB / Redis / metrics secrets from the shared
# aws/secretsmanager key and enables annual rotation.

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_iam_policy_document" "secrets_kms" {
  statement {
    sid     = "RootAccountAdmin"
    actions = ["kms:*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    resources = ["*"]
  }

  # Principals already authorized for Secrets Manager may use this key only
  # when calling through secretsmanager (ECS GetSecretValue, console, etc.).
  statement {
    sid = "AllowSecretsManagerViaService"
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:CreateGrant",
      "kms:DescribeKey",
    ]
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:CallerAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["secretsmanager.${data.aws_region.current.name}.amazonaws.com"]
    }
  }
}

resource "aws_kms_key" "secrets" {
  description             = "${var.name} Secrets Manager application secrets"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.secrets_kms.json
  tags                    = merge(var.tags, { Name = "${var.name}-secrets" })
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${var.name}-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}
