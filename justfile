# HeadStart — thin wrapper over scripts/. Bare `just` lists every recipe.
# Every recipe delegates to a script in scripts/ so that local dev, CI, and
# cloud agents all execute the exact same code paths.

set shell := ["bash", "-euo", "pipefail", "-c"]

[private]
default:
    @just --list

# Install local toolchains (backend venv + frontend deps + hooks)
setup:
    ./scripts/setup.sh

# Regenerate hashed backend lockfiles from pyproject.toml (XCT-14)
lock-backend:
    ./scripts/lock-backend.sh

# Build and start the full stack (docker compose)
up:
    ./scripts/dev.sh up

# Stop the full stack
down:
    ./scripts/dev.sh down

# Restart the full stack
restart:
    ./scripts/dev.sh restart

# Tail logs from all services
logs:
    ./scripts/dev.sh logs

# Show running services
ps:
    ./scripts/dev.sh ps

# Run backend + frontend locally (no docker) for fast iteration
dev:
    ./scripts/dev.sh local

# Run all tests; scope with --backend | --frontend | --scripts
test *args:
    ./scripts/test.sh {{ args }}

# Apply all migrations to a disposable Postgres (needs docker; CI runs this)
test-migrations:
    ./scripts/test-migrations.sh

# Lint all code; scope with --backend | --frontend
lint *args:
    ./scripts/lint.sh {{ args }}

# Auto-format all code
format:
    ./scripts/format.sh

# Type-check all code; scope with --backend | --frontend
typecheck *args:
    ./scripts/typecheck.sh {{ args }}

# Frontend npm audit (high+); also runs in CI after npm ci (FRO-12)
audit-frontend:
    ./scripts/audit-frontend.sh

# Backend pip-audit on hashed lockfiles; also runs in CI after install (OPS-19)
audit-backend:
    ./scripts/audit-backend.sh

# Run the full quality gate (lint + types + tests); scope with --backend | --frontend | --scripts
check *args:
    ./scripts/check.sh {{ args }}

# Frontend SPA production build (tsc + vite); CI uses this (OPS-22)
build-frontend:
    ./scripts/build-frontend.sh

# Apply database migrations
migrate:
    ./scripts/db-migrate.sh upgrade

# Autogenerate a migration: just makemigration "message"
makemigration m:
    ./scripts/db-migrate.sh revision "{{ m }}"

# Load example data
seed:
    ./scripts/seed.sh

# Regenerate landing page product screenshots (needs `just dev` running)
marketing-screenshots:
    PYTHONPATH=backend backend/.venv/bin/python ./scripts/capture_marketing_screenshots.py

# Build container images
build:
    ./scripts/build-images.sh

# Build and push images to a registry (ECR)
push:
    ./scripts/build-images.sh --push

# Deploy to AWS (build, push, update ECS)
deploy:
    ./scripts/deploy.sh

# Create S3 + DynamoDB for Terraform remote state: just terraform-bootstrap yourname [region]
terraform-bootstrap prefix aws_region="":
    ./scripts/terraform-bootstrap-state.sh "{{ prefix }}" "{{ aws_region }}"

# Print exports for deploy: eval "$(just aws-deploy-env beta)"
aws-deploy-env environment="beta":
    ./scripts/aws-deploy-env.sh "{{ environment }}"

# First-time AWS deploy: PREFIX=yourname [YES=1 SKIP_*=... DOMAIN_NAME=...] just aws-first-deploy
aws-first-deploy:
    #!/usr/bin/env bash
    set -euo pipefail
    yes_flag=""
    if [ "${YES:-}" = "1" ]; then yes_flag="--yes"; fi
    AWS_REGION="${AWS_REGION:-us-east-2}" ENVIRONMENT="${ENVIRONMENT:-beta}" \
        ./scripts/aws-first-deploy.sh ${yes_flag}

# Start local llama.cpp server for AI summaries (needs LLAMACPP_MODEL_PATH)
llamacpp:
    ./scripts/llamacpp-dev.sh
