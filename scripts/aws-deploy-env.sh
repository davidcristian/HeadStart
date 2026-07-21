#!/usr/bin/env bash
# Print shell exports for AWS deploy from Terraform outputs.
#
# Usage:
#   eval "$(./scripts/aws-deploy-env.sh beta)"
#   just deploy
#
# Values are emitted with printf %q so a terraform/aws output containing a
# single quote (or other metacharacters) cannot break the eval'd string.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

ENVIRONMENT="${1:-beta}"
TF_DIR="${REPO_ROOT}/devops/terraform/environments/${ENVIRONMENT}"

[[ -d "${TF_DIR}" ]] || die "Unknown environment '${ENVIRONMENT}' (missing ${TF_DIR})"
have terraform || die "terraform is required."
have aws || die "AWS CLI is required."

REGION="$(terraform -chdir="${TF_DIR}" output -raw region 2>/dev/null || true)"
[[ -n "${REGION}" ]] || REGION="${AWS_REGION:-us-east-2}"

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
ECS_CLUSTER="$(terraform -chdir="${TF_DIR}" output -raw ecs_cluster_name)"
APP_URL="$(terraform -chdir="${TF_DIR}" output -raw app_url 2>/dev/null || echo "http://$(terraform -chdir="${TF_DIR}" output -raw alb_dns_name)")"

printf "export AWS_REGION=%q\n" "${REGION}"
printf "export ENVIRONMENT=%q\n" "${ENVIRONMENT}"
printf "export ECR_REGISTRY=%q\n" "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
printf "export ECS_CLUSTER=%q\n" "${ECS_CLUSTER}"
printf "export APP_URL=%q\n" "${APP_URL}"
