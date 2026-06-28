#!/usr/bin/env bash
# Deploy to AWS: build + push images, then roll ECS services to the new tag.
# Intended to be run by CI (with an assumed AWS role) or locally with creds.
#
# Env:
#   ENVIRONMENT    target env dir under devops/terraform/environments (default: dev)
#   AWS_REGION     required
#   ECR_REGISTRY   required
#   ECS_CLUSTER    required (ECS cluster name; usually a Terraform output)
#   IMAGE_TAG      optional (default: git short sha)
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

ENVIRONMENT="${ENVIRONMENT:-dev}"
: "${AWS_REGION:?AWS_REGION is required}"
: "${ECR_REGISTRY:?ECR_REGISTRY is required}"
: "${ECS_CLUSTER:?ECS_CLUSTER is required}"
export IMAGE_TAG="${IMAGE_TAG:-$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo latest)}"

log "Deploying tag ${IMAGE_TAG} to environment '${ENVIRONMENT}'"

# 1) Build + push images.
"${REPO_ROOT}/scripts/build-images.sh" --push

# 2) Run migrations as a one-off ECS task (task def 'jobnotifier-migrate').
log "Running database migrations (one-off ECS task)"
aws ecs run-task \
  --cluster "${ECS_CLUSTER}" \
  --task-definition jobnotifier-migrate \
  --launch-type FARGATE \
  --region "${AWS_REGION}" >/dev/null || warn "migrate task submission failed; check logs"

# 3) Force a new deployment of each long-running service.
for svc in api frontend worker beat; do
  log "Updating service jobnotifier-${svc}"
  aws ecs update-service \
    --cluster "${ECS_CLUSTER}" \
    --service "jobnotifier-${svc}" \
    --force-new-deployment \
    --region "${AWS_REGION}" >/dev/null
done

ok "Deploy triggered for tag ${IMAGE_TAG}. ECS is rolling the services."
