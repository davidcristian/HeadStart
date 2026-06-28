# 0003. Deployment on AWS ECS Fargate via Terraform

- **Status:** Accepted
- **Date:** 2026-06-28

## Context

The user wants deployable containers on AWS, managed with Terraform in a
`devops/` folder, and explicitly ruled out Kubernetes. They also want to keep the
option to run everything locally for free.

## Decision

- **Compute:** AWS ECS Fargate. Serverless containers, no node management, a good
  fit for a small always-on set of services (api, frontend, worker, beat).
- **Database:** RDS Postgres. **Broker:** ElastiCache Redis.
- **Edge:** Application Load Balancer routing to the api and frontend services.
- **IaC:** Terraform under `devops/terraform/`, split into reusable `modules/`
  and `environments/{dev,prod}` with remote state in S3 + DynamoDB locking.
- **Secrets:** AWS Secrets Manager / SSM Parameter Store, injected into tasks.

The same container images run locally via Docker Compose; only orchestration
differs. Local development never depends on `devops/`.

## Consequences

- Lower ops burden than k8s; still scalable per-service.
- Some AWS lock-in (ECS task defs, ALB). Mitigated by keeping app code
  cloud-agnostic and all AWS specifics inside `devops/`.
- Cost when running 24/7; the free local path remains for cost-sensitive use.

## Alternatives considered

- **Kubernetes (EKS):** ruled out by the user; heavier ops.
- **Fly.io / Railway / Render:** simpler, but the user specifically wants AWS +
  Terraform.
- **Single EC2 + docker compose:** cheapest, but less resilient and not the
  requested managed-container model.
