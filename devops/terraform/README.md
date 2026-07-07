# Terraform (AWS deployment)

Provisions HeadStart on AWS ECS Fargate.

- **First-time deploy walkthrough:** [../../docs/deploying-to-aws.md](../../docs/deploying-to-aws.md)
- **Architecture / module layout:** [../../docs/modules/deployment.md](../../docs/modules/deployment.md)

## Layout

```
modules/
  network/   security/   ecr/   secrets/   iam/   alb/   rds/   redis/   ecs/
  stack/     # composes all of the above into one environment
environments/
  dev/   prod/   # thin wrappers: provider + remote state + module "stack"
```

## One-time bootstrap (remote state)

State lives in S3 with a DynamoDB lock table. Create them once from the repo root:

```bash
make terraform-bootstrap PREFIX=YOURNAME AWS_REGION=us-east-2
```

Then set the bucket name in `environments/<env>/backend.tf` (replace `CHANGEME`),
or use `make aws-first-deploy` which passes the bucket via `-backend-config`.

## First-time deploy (one command)

From the repo root (AWS creds + Terraform + Docker required):

```bash
make aws-first-deploy PREFIX=YOURNAME AWS_REGION=us-east-2
```

See [../../docs/deploying-to-aws.md](../../docs/deploying-to-aws.md#quick-start-one-command).

## Deploy an environment

```bash
cd environments/beta
export TF_VAR_db_password="$(openssl rand -base64 24)"
export TF_VAR_jwt_secret="$(openssl rand -hex 32)"
export TF_VAR_credentials_secret_key="$(openssl rand -hex 32)"
terraform init
terraform plan
terraform apply
```

Outputs include `app_url`, `alb_dns_name`, and `ecr_repository_urls`.

## First image push + migrations

The ECS services need images in ECR before they can run. From the repo root:

```bash
eval "$(make aws-deploy-env)"
make deploy
```

## Conventions

- Secrets are never committed. Provide them via `TF_VAR_*` env vars or a local
  `terraform.tfvars` (gitignored). They are stored in AWS Secrets Manager and
  injected into ECS tasks at runtime.
- `prod` enables Multi-AZ RDS, 30-day DB backups, 90-day ECS log retention,
  deletion protection, and Multi-AZ Redis with automatic failover; `beta` stays
  minimal/cheap (7-day backups, 30-day logs, single-node Redis).
- Prod `image_tag` is required and must not be `latest` (immutable git SHA pin;
  OPS-07). Beta may still default to `latest` for throwaway stacks; `deploy.sh`
  retargets task defs to `IMAGE_TAG` on every roll either way.
- ECS service + task family names are stable (`headstart-api`, etc.) so the
  same `deploy.sh` works against any environment's cluster. `deploy.sh`
  registers a new task-definition revision per family pinned to the just-pushed
  `IMAGE_TAG` before rolling services (Terraform's `image_tag` is only the
  initial pin; ECS `ignore_changes` on `task_definition` leaves rolls to deploy).
