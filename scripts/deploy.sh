#!/usr/bin/env bash
# Deploy to AWS: build + push images, then register ECS task defs pinned to the
# freshly pushed tag *and* ECR content digest, and roll services onto those
# revisions.
# Migrations must finish successfully before any service roll.
# Intended to be run by CI (with an assumed AWS role) or locally with creds.
#
# Env:
#   ENVIRONMENT    target env dir under devops/terraform/environments (default: beta)
#   AWS_REGION     required
#   ECR_REGISTRY   required
#   ECS_CLUSTER    required (ECS cluster name; usually a Terraform output)
#   IMAGE_TAG      optional (default: git short sha)
#   SERVICE_PREFIX optional (default: headstart; ECS family/service name prefix)
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

ENVIRONMENT="${ENVIRONMENT:-beta}"
SERVICE_PREFIX="${SERVICE_PREFIX:-headstart}"
: "${AWS_REGION:?AWS_REGION is required}"
: "${ECR_REGISTRY:?ECR_REGISTRY is required}"
: "${ECS_CLUSTER:?ECS_CLUSTER is required}"
export IMAGE_TAG="${IMAGE_TAG:-$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo latest)}"

have aws || die "aws CLI is required"

# Resolve the ECR content digest for a just-pushed ``IMAGE_TAG``.
ecr_image_digest() {
  local repo="$1"
  local digest
  digest="$(
    aws ecr describe-images \
      --repository-name "${repo}" \
      --image-ids "imageTag=${IMAGE_TAG}" \
      --region "${AWS_REGION}" \
      --query 'imageDetails[0].imageDigest' \
      --output text
  )" || die "failed to describe ECR image ${repo}:${IMAGE_TAG}"
  [[ -n "${digest}" && "${digest}" != "None" && "${digest}" == sha256:* ]] \
    || die "ECR returned no sha256 digest for ${repo}:${IMAGE_TAG}"
  printf '%s\n' "${digest}"
}

# Map a task family to the digest resolved after push for its ECR repository.
digest_for_family() {
  local family="$1"
  case "${family}" in
    *-api|*-beat|*-migrate) printf '%s\n' "${DIGEST_BACKEND}" ;;
    *-worker) printf '%s\n' "${DIGEST_WORKER}" ;;
    *-frontend) printf '%s\n' "${DIGEST_FRONTEND}" ;;
    *) die "unknown task family for image digest: ${family}" ;;
  esac
}

# Register a new revision of ``family`` with every container image pinned to
# ``IMAGE_TAG@sha256:…``, then print the new taskDefinitionArn on stdout.
register_retargeted_task_def() {
  local family="$1"
  local described register_payload new_arn digest
  digest="$(digest_for_family "${family}")"
  described="$(aws ecs describe-task-definition \
    --task-definition "${family}" \
    --region "${AWS_REGION}" \
    --output json)" \
    || die "failed to describe task definition ${family}"

  register_payload="$(
    printf '%s' "${described}" | py -m app.cli.ecs_task_def retarget \
      --ecr-registry "${ECR_REGISTRY}" \
      --family "${family}" \
      --image-tag "${IMAGE_TAG}" \
      --image-digest "${digest}"
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

# Submit a one-off migrate task, wait until it stops, and abort unless every
# container exited 0. A failed or partial schema then never rolls new app images.
run_and_await_migrate_task() {
  local task_def_arn="$1"
  local run_out task_arn exit_codes code
  run_out="$(
    aws ecs run-task \
      --cluster "${ECS_CLUSTER}" \
      --task-definition "${task_def_arn}" \
      --launch-type FARGATE \
      --region "${AWS_REGION}" \
      --output json
  )" || die "failed to submit migrate task"

  task_arn="$(
    printf '%s' "${run_out}" | py -c '
import json, sys
data = json.load(sys.stdin)
failures = data.get("failures") or []
if failures:
    raise SystemExit(f"migrate run-task failures: {failures!r}")
tasks = data.get("tasks") or []
if not tasks or not tasks[0].get("taskArn"):
    raise SystemExit("migrate run-task returned no task ARN")
print(tasks[0]["taskArn"])
'
  )" || die "could not parse migrate task ARN from run-task response"

  log "Waiting for migrate task to stop: ${task_arn}"
  aws ecs wait tasks-stopped \
    --cluster "${ECS_CLUSTER}" \
    --tasks "${task_arn}" \
    --region "${AWS_REGION}" \
    || die "timed out waiting for migrate task ${task_arn}"

  exit_codes="$(
    aws ecs describe-tasks \
      --cluster "${ECS_CLUSTER}" \
      --tasks "${task_arn}" \
      --region "${AWS_REGION}" \
      --query 'tasks[0].containers[*].exitCode' \
      --output text
  )" || die "failed to describe migrate task ${task_arn}"

  [[ -n "${exit_codes}" && "${exit_codes}" != "None" ]] \
    || die "migrate task ${task_arn} has no container exit codes; aborting service roll"

  for code in ${exit_codes}; do
    [[ "${code}" == "0" ]] \
      || die "migrate task failed (exitCode=${code}, task=${task_arn}); aborting service roll"
  done
  ok "Migrations completed successfully (task ${task_arn})"
}

log "Deploying tag ${IMAGE_TAG} to environment '${ENVIRONMENT}'"

# 1) Build + push images.
"${REPO_ROOT}/scripts/build-images.sh" --push

# 2) Resolve ECR content digests for the just-pushed tags so task defs pin the
#    exact manifest this pipeline built (not only a mutable-or-floating tag).
log "Resolving ECR image digests for tag ${IMAGE_TAG}"
DIGEST_BACKEND="$(ecr_image_digest "headstart-backend")"
DIGEST_WORKER="$(ecr_image_digest "headstart-backend-worker")"
DIGEST_FRONTEND="$(ecr_image_digest "headstart-frontend")"
ok "Pinned digests: backend=${DIGEST_BACKEND} worker=${DIGEST_WORKER} frontend=${DIGEST_FRONTEND}"

# 3) Run migrations as a one-off ECS task on a revision pinned to tag@digest.
#    Wait for completion and require exit 0 before any service roll.
log "Running database migrations (one-off ECS task)"
migrate_td="$(register_retargeted_task_def "${SERVICE_PREFIX}-migrate")"
log "Registered migrate revision: ${migrate_td}"
run_and_await_migrate_task "${migrate_td}"

# 4) Register a digest-pinned revision per long-running service, then roll onto it.
#    Force-new-deployment alone would re-pull the Terraform-pinned tag (often
#    ``latest``), which build-images.sh never re-pushes, leaving new code
#    unshipped. ECS services ignore Terraform task_definition changes after
#    first apply; deploy owns the image pin at roll time.
for svc in api frontend worker beat; do
  family="${SERVICE_PREFIX}-${svc}"
  log "Registering ${family} pinned to ${IMAGE_TAG}@digest"
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

ok "Deploy triggered for tag ${IMAGE_TAG} (digest-pinned). ECS is rolling the services."
