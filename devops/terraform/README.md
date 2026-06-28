# Terraform (AWS deployment)

Provisions JobNotifier on AWS ECS Fargate. See
[../../docs/modules/deployment.md](../../docs/modules/deployment.md) for the
architecture overview.

## Layout

```
modules/
  network/   security/   ecr/   secrets/   iam/   alb/   rds/   redis/   ecs/
  stack/     # composes all of the above into one environment
environments/
  dev/   prod/   # thin wrappers: provider + remote state + module "stack"
```

## One-time bootstrap (remote state)

State lives in S3 with a DynamoDB lock table. Create them once (any method):

```bash
aws s3api create-bucket --bucket CHANGEME-jobnotifier-tfstate \
  --region eu-central-1 --create-bucket-configuration LocationConstraint=eu-central-1
aws s3api put-bucket-versioning --bucket CHANGEME-jobnotifier-tfstate \
  --versioning-configuration Status=Enabled
aws dynamodb create-table --table-name jobnotifier-tflock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST --region eu-central-1
```

Then set the bucket name in `environments/<env>/backend.tf` (replace `CHANGEME`).

## Deploy an environment

```bash
cd environments/dev
export TF_VAR_db_password="$(openssl rand -base64 24)"
export TF_VAR_jwt_secret="$(openssl rand -hex 32)"
export TF_VAR_credentials_secret_key="$(openssl rand -hex 32)"
terraform init
terraform plan
terraform apply
```

Outputs include `alb_dns_name` (the public URL) and `ecr_repository_urls`.

## First image push + migrations

The ECS services need images in ECR before they can run. Build and push, then
run migrations and roll the services (this is exactly what `scripts/deploy.sh`
does in CI):

```bash
export AWS_REGION=eu-central-1
export ECR_REGISTRY=<account-id>.dkr.ecr.eu-central-1.amazonaws.com
export ECS_CLUSTER=$(terraform output -raw ecs_cluster_name)
../../../scripts/deploy.sh
```

## Conventions

- Secrets are never committed. Provide them via `TF_VAR_*` env vars or a local
  `terraform.tfvars` (gitignored). They are stored in AWS Secrets Manager and
  injected into ECS tasks at runtime.
- `prod` enables Multi-AZ RDS and deletion protection; `dev` is minimal/cheap.
- ECS service + task family names are stable (`jobnotifier-api`, etc.) so the
  same `deploy.sh` works against any environment's cluster.
