# Customer-managed KMS key for RDS storage + Performance Insights (OPS-43).
# Isolates encryption from the shared aws/rds key and enables annual rotation.

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "rds_kms" {
  statement {
    sid     = "RootAccountAdmin"
    actions = ["kms:*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    resources = ["*"]
  }

  statement {
    sid = "AllowRDSUseOfTheKey"
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:CreateGrant",
      "kms:DescribeKey",
    ]
    principals {
      type        = "Service"
      identifiers = ["rds.amazonaws.com"]
    }
    resources = ["*"]
  }

  statement {
    sid = "AllowRDSGrants"
    actions = [
      "kms:CreateGrant",
      "kms:ListGrants",
      "kms:RevokeGrant",
    ]
    principals {
      type        = "Service"
      identifiers = ["rds.amazonaws.com"]
    }
    resources = ["*"]
    condition {
      test     = "Bool"
      variable = "kms:GrantIsForAWSResource"
      values   = ["true"]
    }
  }
}

resource "aws_kms_key" "rds" {
  description             = "${var.name} RDS storage and Performance Insights"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.rds_kms.json
  tags                    = merge(var.tags, { Name = "${var.name}-rds" })
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${var.name}-rds"
  target_key_id = aws_kms_key.rds.key_id
}
