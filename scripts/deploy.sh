#!/usr/bin/env bash
# Deploy to AWS: build + push images, then register ECS task defs pinned to the
# freshly pushed tag and roll services onto those revisions (OPS-01).
# Intended to be run by CI (with an assumed AWS role) or locally with creds.
#
# Env:
#   ENVIRONMENT    target env dir under devops/terraform/environments (default: beta)
#   AWS_REGION     required
#   ECR_REGISTRY   required
#   ECS_CLUSTER    required (ECS cluster name; usually a Terraform output)
#   IMAGE_TAG      optional (default: git short sha)
#   SERVICE_PREFIX optional (default: headstart) — ECS family/service name prefix
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

ENVIRONMENT="${ENVIRONMENT:-beta}"
SERVICE_PREFIX="${SERVICE_PREFIX:-headstart}"
: "${AWS_REGION:?AWS_REGION is required}"
: "${ECR_REGISTRY:?ECR_REGISTRY is required}"
: "${ECS_CLUSTER:?ECS_CLUSTER is required}"
export IMAGE_TAG="${IMAGE_TAG:-$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo latest)}"

have aws || die "aws CLI is required"

# Register a new revision of ``family`` with every container image pinned to
# ``IMAGE_TAG``, then print the new taskDefinitionArn on stdout.
register_retargeted_task_def() {
  local family="$1"
  local described register_payload new_arn
  described="$(aws ecs describe-task-definition \
    --task-definition "${family}" \
    --region "${AWS_REGION}" \
    --output json)" \
    || die "failed to describe task definition ${family}"

  register_payload="$(
    printf '%s' "${described}" | py -m app.cli.ecs_task_def retarget \
      --ecr-registry "${ECR_REGISTRY}" \
      --family "${family}" \
      --image-tag "${IMAGE_TAG}"
  )" || die "failed to retarget task definition ${family}"

  new_arn="$(
    printf '%s' "${register_payload}" \
      | aws ecs register-task-definition \
          --cli-input-json file:///dev/stdin \
          --region "${AWS_REGION}" \
          --query 'taskDefinition.taskDefinitionArn' \
          --output text
  )" || die "failed to register task definition ${family}"

  [[ -n "${new_arn}" && "${new_arn}" != "None" ]] \
    || die "register-task-definition returned empty ARN for ${family}"
  printf '%s\n' "${new_arn}"
}

log "Deploying tag ${IMAGE_TAG} to environment '${ENVIRONMENT}'"

# 1) Build + push images.
"${REPO_ROOT}/scripts/build-images.sh" --push

# 2) Run migrations as a one-off ECS task on a revision pinned to IMAGE_TAG.
log "Running database migrations (one-off ECS task)"
migrate_td="$(register_retargeted_task_def "${SERVICE_PREFIX}-migrate")"
log "Registered migrate revision: ${migrate_td}"
aws ecs run-task \
  --cluster "${ECS_CLUSTER}" \
  --task-definition "${migrate_td}" \
  --launch-type FARGATE \
  --region "${AWS_REGION}" >/dev/null || warn "migrate task submission failed; check logs"

# 3) Register a SHA-pinned revision per long-running service, then roll onto it.
#    Force-new-deployment alone would re-pull the Terraform-pinned tag (often
#    ``latest``), which build-images.sh never re-pushes — so new code would not
#    ship. ECS services ignore Terraform task_definition changes after first
#    apply; deploy owns the image pin at roll time.
for svc in api frontend worker beat; do
  family="${SERVICE_PREFIX}-${svc}"
  log "Registering ${family} pinned to ${IMAGE_TAG}"
  new_td="$(register_retargeted_task_def "${family}")"
  log "Updating service ${family} -> ${new_td}"
  aws ecs update-service \
    --cluster "${ECS_CLUSTER}" \
    --service "${family}" \
    --task-definition "${new_td}" \
    --force-new-deployment \
    --region "${AWS_REGION}" >/dev/null \
    || die "failed to update service ${family}"
done

ok "Deploy triggered for tag ${IMAGE_TAG}. ECS is rolling the services."
