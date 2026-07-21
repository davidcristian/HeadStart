provider "aws" {
  region              = var.region
  # Fail fast when ambient credentials target the wrong account.
  allowed_account_ids = [var.aws_account_id]
}
