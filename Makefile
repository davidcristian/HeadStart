# JobNotifier - thin wrapper over scripts/. Run `make help` for the list.
# Every target delegates to a script in scripts/ so that local dev, CI, and
# cloud agents all execute the exact same code paths.

SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help setup up down logs dev test lint format typecheck check \
        migrate makemigration seed build push deploy ps restart \
        terraform-bootstrap aws-deploy-env aws-first-deploy marketing-screenshots

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Install local toolchains (backend venv + frontend deps + hooks)
	./scripts/setup.sh

up: ## Build and start the full stack (docker compose)
	./scripts/dev.sh up

down: ## Stop the full stack
	./scripts/dev.sh down

restart: ## Restart the full stack
	./scripts/dev.sh restart

logs: ## Tail logs from all services
	./scripts/dev.sh logs

ps: ## Show running services
	./scripts/dev.sh ps

dev: ## Run backend + frontend locally (no docker) for fast iteration
	./scripts/dev.sh local

test: ## Run all tests (backend + frontend)
	./scripts/test.sh

lint: ## Lint all code
	./scripts/lint.sh

format: ## Auto-format all code
	./scripts/format.sh

typecheck: ## Type-check all code
	./scripts/typecheck.sh

check: lint typecheck test ## Run the full quality gate (lint + types + tests)

migrate: ## Apply database migrations
	./scripts/db-migrate.sh upgrade

makemigration: ## Autogenerate a migration: make makemigration m="message"
	./scripts/db-migrate.sh revision "$(m)"

seed: ## Load example data
	./scripts/seed.sh

marketing-screenshots: ## Regenerate landing page product screenshots (needs make dev)
	PYTHONPATH=backend backend/.venv/bin/python ./scripts/capture_marketing_screenshots.py

build: ## Build container images
	./scripts/build-images.sh

push: ## Build and push images to a registry (ECR)
	./scripts/build-images.sh --push

deploy: ## Deploy to AWS (build, push, update ECS)
	./scripts/deploy.sh

terraform-bootstrap: ## Create S3 + DynamoDB for Terraform remote state (PREFIX=yourname)
	./scripts/terraform-bootstrap-state.sh "$(PREFIX)" "$(AWS_REGION)"

aws-deploy-env: ## Print exports for deploy (ENVIRONMENT=dev): eval "$$(make aws-deploy-env)"
	./scripts/aws-deploy-env.sh "$(or $(ENVIRONMENT),dev)"

aws-first-deploy: ## First-time AWS deploy (PREFIX=yourname): bootstrap + terraform + deploy
	PREFIX="$(PREFIX)" AWS_REGION="$(or $(AWS_REGION),us-east-2)" \
	ENVIRONMENT="$(or $(ENVIRONMENT),dev)" YES="$(YES)" \
	SKIP_BOOTSTRAP="$(SKIP_BOOTSTRAP)" SKIP_DEPLOY="$(SKIP_DEPLOY)" \
	DOMAIN_NAME="$(DOMAIN_NAME)" ROUTE53_ZONE_ID="$(ROUTE53_ZONE_ID)" \
	./scripts/aws-first-deploy.sh $(if $(filter 1,$(YES)),--yes,)
