# Deploying to AWS

Step-by-step guide for a **first-time** deploy of JobNotifier to AWS ECS Fargate.
For architecture and Terraform module layout, see
[modules/deployment.md](modules/deployment.md).

Local development is documented in [runbook.md](runbook.md) and
[getting-started.md](getting-started.md). After deploy, use
[getting-started.md](getting-started.md) from step 2 onward — only the URLs
change.

---

## What gets created

Terraform (`devops/terraform/`) provisions:

- VPC, subnets, security groups
- Application Load Balancer (public HTTP entrypoint)
- ECS Fargate cluster with services: `api`, `frontend`, `worker`, `beat`
- RDS Postgres + ElastiCache Redis
- ECR repositories for backend, backend-worker (Playwright), and frontend images
- Secrets Manager entries for `POSTGRES_PASSWORD`, `JWT_SECRET`,
  `CREDENTIALS_SECRET_KEY`

Default region is **`us-east-2`**. Use the **`dev`** environment first (cheaper);
**`prod`** adds Multi-AZ RDS and deletion protection.

> **Cost:** even `dev` runs an ALB, four Fargate tasks, RDS, and Redis — expect
> ongoing monthly charges, not a free-tier-only stack.

> **HTTPS:** the ALB serves **HTTP on port 80** today. Port 443 is open in the
> security group, but there is no TLS listener or certificate yet. You access the
> app at `http://<alb-dns-name>`. Custom domain + HTTPS is a follow-up task.

---

## Prerequisites

On the machine that will run Terraform and build images:

| Tool | Install |
| ---- | ------- |
| AWS CLI v2 | [AWS install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| Terraform | [HashiCorp install guide](https://developer.hashicorp.com/terraform/install) |
| Docker | engine + `docker compose` plugin |
| `make`, `git`, `openssl` | usually preinstalled |

Configure AWS credentials so this works:

```bash
aws sts get-caller-identity
```

Your IAM principal needs broad permissions for the first `terraform apply` (VPC,
ECS, RDS, ElastiCache, ALB, IAM, Secrets Manager, ECR). `AdministratorAccess`
is simplest for a personal first deploy; tighten later.

---

## 1. Bootstrap remote state (one-time)

Terraform state lives in S3 with a DynamoDB lock table. Create them once.
Replace `YOURNAME` with a globally unique prefix:

```bash
export AWS_REGION=us-east-2

aws s3api create-bucket \
  --bucket YOURNAME-jobnotifier-tfstate \
  --region us-east-2 \
  --create-bucket-configuration LocationConstraint=us-east-2

aws s3api put-bucket-versioning \
  --bucket YOURNAME-jobnotifier-tfstate \
  --versioning-configuration Status=Enabled

aws dynamodb create-table \
  --table-name jobnotifier-tflock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-2
```

Edit `devops/terraform/environments/dev/backend.tf` and replace
`CHANGEME-jobnotifier-tfstate` with your bucket name. Do the same in
`environments/prod/backend.tf` when you add production.

---

## 2. Provision infrastructure

```bash
cd devops/terraform/environments/dev

# Save these somewhere safe — you cannot recover them from Terraform output.
export TF_VAR_db_password="$(openssl rand -base64 24)"
export TF_VAR_jwt_secret="$(openssl rand -hex 32)"
export TF_VAR_credentials_secret_key="$(openssl rand -hex 32)"

# Optional but recommended: unguessable default ntfy topic.
export TF_VAR_ntfy_default_topic="jobs-$(openssl rand -hex 4)"

terraform init
terraform plan
terraform apply
```

Secrets are written to **AWS Secrets Manager** and injected into ECS tasks at
runtime. Never commit them to git. You can also use a local `terraform.tfvars`
(gitignored); see `terraform.tfvars.example` in the same directory.

Note the outputs:

```bash
terraform output alb_dns_name        # public URL (HTTP)
terraform output ecs_cluster_name    # e.g. jobnotifier-dev
terraform output ecr_repository_urls
```

ECS services will not become healthy until images exist in ECR (next step).

---

## 3. Build, push, and roll services

From the **repository root**, with Docker running:

```bash
export AWS_REGION=us-east-2
export ENVIRONMENT=dev

export ECR_REGISTRY="$(aws sts get-caller-identity --query Account --output text).dkr.ecr.${AWS_REGION}.amazonaws.com"
export ECS_CLUSTER="$(cd devops/terraform/environments/dev && terraform output -raw ecs_cluster_name)"

make deploy
```

`make deploy` runs `scripts/deploy.sh`, which:

1. Builds backend images (`scripts/build-images.sh --push`): lean API/beat image
   plus the Playwright-enabled worker image, and the frontend image
2. Pushes them to ECR (tag = current git short SHA, or `latest` if not in git)
3. Runs DB migrations as a one-off ECS task (`jobnotifier-migrate`)
4. Forces a rolling deploy of `jobnotifier-api`, `jobnotifier-frontend`,
   `jobnotifier-worker`, and `jobnotifier-beat`

Verify rollout:

```bash
aws ecs describe-services \
  --cluster "$ECS_CLUSTER" \
  --services jobnotifier-api jobnotifier-frontend jobnotifier-worker jobnotifier-beat \
  --region "$AWS_REGION" \
  --query 'services[*].[serviceName,runningCount,desiredCount,deployments[0].rolloutState]' \
  --output table
```

Health check (replace with your ALB DNS name):

```bash
curl "http://$(cd devops/terraform/environments/dev && terraform output -raw alb_dns_name)/api/v1/health"
```

---

## 4. Use the app

Open the ALB DNS name in a browser:

- **UI:** `http://<alb-dns>/`
- **API docs:** `http://<alb-dns>/docs`

There is no `make seed` on AWS. Continue with
[getting-started.md](getting-started.md) from **step 2** (create your account).
The first registered user becomes admin.

---

## Ongoing deploys

After infrastructure exists, ship code changes with:

```bash
export AWS_REGION=us-east-2
export ECR_REGISTRY="<account-id>.dkr.ecr.us-east-2.amazonaws.com"
export ECS_CLUSTER=jobnotifier-dev   # or jobnotifier-prod
export ENVIRONMENT=dev               # optional; default is dev

make deploy
```

Migrations run automatically on each deploy.

---

## Production (`prod` environment)

When ready for production:

1. Update `devops/terraform/environments/prod/backend.tf` with your state bucket.
2. `cd environments/prod` and run `terraform init && terraform apply` with the
   same `TF_VAR_*` secrets pattern.
3. Set `TF_VAR_cors_origins` to your real domain(s) — see
   `prod/terraform.tfvars.example`.
4. Deploy with `ENVIRONMENT=prod` and `ECS_CLUSTER=jobnotifier-prod`.

`prod` uses larger instances, Multi-AZ RDS, and deletion protection on the
database.

---

## CI/CD (deploy optional)

The quality gate (`ci.yml`) runs on every push/PR. The deploy workflow is
manual and guarded on an AWS role variable; it needs an AWS role to assume
and the same application secrets
(`JWT_SECRET`, `CREDENTIALS_SECRET_KEY`) that Terraform stores in Secrets Manager.

---

## Troubleshooting

| Symptom | Likely cause / fix |
| ------- | ------------------ |
| ECS tasks stuck `PENDING` | Images not in ECR yet — run `make deploy` |
| `make deploy` fails on ECR login | `aws sts get-caller-identity` or region mismatch |
| Health check fails | Migrations not finished; check CloudWatch log group `/ecs/jobnotifier-dev` |
| 401 / login loops in UI | API not reachable; confirm ALB routes `/api/*` to the API target group |
| No job notifications | Same as local — ntfy topic mismatch; see [getting-started.md](getting-started.md) |
| `terraform apply` state lock | Another apply in progress, or stale DynamoDB lock row |

Operational debugging (logs, pipeline) is covered in [runbook.md](runbook.md).
