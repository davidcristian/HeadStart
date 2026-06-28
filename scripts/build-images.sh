#!/usr/bin/env bash
# Build (and optionally push) the backend and frontend container images.
#   build-images.sh             -> build locally
#   build-images.sh --push      -> build + push to $ECR_REGISTRY
#
# Env:
#   IMAGE_TAG      (default: git short sha, or 'latest')
#   ECR_REGISTRY   (required for --push) e.g. 123456789012.dkr.ecr.us-east-2.amazonaws.com
#   AWS_REGION     (required for --push)
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

push=false
[[ "${1:-}" == "--push" ]] && push=true

IMAGE_TAG="${IMAGE_TAG:-$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo latest)}"
backend_img="jobnotifier/backend:${IMAGE_TAG}"
frontend_img="jobnotifier/frontend:${IMAGE_TAG}"

log "Building backend image: ${backend_img}"
docker build -t "${backend_img}" "${BACKEND_DIR}"

log "Building frontend image: ${frontend_img}"
docker build -t "${frontend_img}" \
  --build-arg "VITE_API_BASE_URL=${VITE_API_BASE_URL:-/api}" \
  "${FRONTEND_DIR}"

if [[ "${push}" == true ]]; then
  : "${ECR_REGISTRY:?ECR_REGISTRY is required for --push}"
  : "${AWS_REGION:?AWS_REGION is required for --push}"
  log "Logging in to ECR ${ECR_REGISTRY}"
  aws ecr get-login-password --region "${AWS_REGION}" \
    | docker login --username AWS --password-stdin "${ECR_REGISTRY}"
  for name in backend frontend; do
    local_img="jobnotifier/${name}:${IMAGE_TAG}"
    remote_img="${ECR_REGISTRY}/jobnotifier-${name}:${IMAGE_TAG}"
    docker tag "${local_img}" "${remote_img}"
    log "Pushing ${remote_img}"
    docker push "${remote_img}"
  done
  ok "Pushed images with tag ${IMAGE_TAG}."
else
  ok "Built images with tag ${IMAGE_TAG} (local only)."
fi
