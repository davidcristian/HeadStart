#!/usr/bin/env bash
# Bootstrap remote Terraform state (S3 + DynamoDB lock table) for HeadStart.
#
# Usage:
#   ./scripts/terraform-bootstrap-state.sh YOURNAME us-east-2
#
# Then replace CHANGEME in devops/terraform/environments/*/backend.tf with
# YOURNAME-headstart-tfstate.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

PREFIX="${1:-}"
REGION="${2:-us-east-2}"

if [[ -z "${PREFIX}" ]]; then
  die "Usage: $0 <state-bucket-prefix> [aws-region]"
fi

BUCKET="${PREFIX}-headstart-tfstate"
LOCK_TABLE="headstart-tflock"

have aws || die "AWS CLI is required."

log "Creating S3 bucket ${BUCKET} in ${REGION}"
if aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
  warn "Bucket ${BUCKET} already exists — skipping create"
else
  if [[ "${REGION}" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "${BUCKET}" --region "${REGION}"
  else
    aws s3api create-bucket \
      --bucket "${BUCKET}" \
      --region "${REGION}" \
      --create-bucket-configuration "LocationConstraint=${REGION}"
  fi
fi

log "Enabling versioning on ${BUCKET}"
aws s3api put-bucket-versioning \
  --bucket "${BUCKET}" \
  --versioning-configuration Status=Enabled

log "Creating DynamoDB lock table ${LOCK_TABLE}"
if aws dynamodb describe-table --table-name "${LOCK_TABLE}" --region "${REGION}" >/dev/null 2>&1; then
  warn "Table ${LOCK_TABLE} already exists — skipping create"
else
  aws dynamodb create-table \
    --table-name "${LOCK_TABLE}" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "${REGION}"
fi

ok "Remote state bootstrap complete."
echo
echo "Next steps:"
echo "  1. Set bucket name in devops/terraform/environments/beta/backend.tf:"
echo "       bucket = \"${BUCKET}\""
echo "  2. Repeat for environments/prod/backend.tf when you add production."
echo "  3. cd devops/terraform/environments/beta && terraform init && terraform apply"
