# Deploying to AWS

Step-by-step guide for a **first-time** deploy of HeadStart to AWS ECS Fargate.
For architecture and Terraform module layout, see
[modules/deployment.md](modules/deployment.md).

Local development is documented in [runbook.md](runbook.md) and
[getting-started.md](getting-started.md). After deploy, use
[getting-started.md](getting-started.md) from step 2 onward — only the URLs
change.

---

## Quick start (one command)

If you have AWS credentials, Terraform, and Docker configured, you can run the
full first-time path from the **repository root**:

```bash
export AWS_REGION=us-east-2
make aws-first-deploy PREFIX=your-unique-name
```

This single command:

1. Creates the remote Terraform state bucket + DynamoDB lock table (if missing)
2. Generates application secrets and saves them to `.aws-first-deploy-secrets.env`
   (gitignored — back them up)
3. Runs `terraform init` (with `-backend-config` so you do not need to edit
   `backend.tf`) and `terraform apply`
4. Builds container images, pushes to ECR, runs migrations, and rolls ECS services

Add `YES=1` to skip the terraform confirmation prompt (useful in automation).
Add `SKIP_DEPLOY=1` to provision infrastructure only (no Docker image push).

Optional HTTPS during first deploy (Route53 hosted zone required):

```bash
make aws-first-deploy PREFIX=yourname \
  DOMAIN_NAME=jobs.example.com \
  ROUTE53_ZONE_ID=Z0123456789ABCDEFGHIJ \
  YES=1
```

Verify prerequisites without making changes:

```bash
./scripts/aws-first-deploy.sh --check
```

The sections below walk through the same steps manually if you prefer more
control or need to troubleshoot.

---

## What gets created

Terraform (`devops/terraform/`) provisions:

- VPC, subnets, security groups
- Application Load Balancer (public entrypoint; HTTP by default, optional HTTPS)
- ECS Fargate cluster with services: `api`, `frontend`, `worker`, `beat`
- RDS Postgres + ElastiCache Redis
- ECR repositories for backend, backend-worker (Playwright), and frontend images
- Secrets Manager entries for `POSTGRES_PASSWORD`, `JWT_SECRET`,
  `CREDENTIALS_SECRET_KEY`

Default region is **`us-east-2`**. Use the **`dev`** environment first (cheaper);
**`prod`** adds Multi-AZ RDS and deletion protection.

> **Cost:** even `dev` runs an ALB, four Fargate tasks, RDS, and Redis — expect
> ongoing monthly charges, not a free-tier-only stack.

> **HTTPS:** without a custom domain the ALB serves **HTTP on port 80** at
> `http://<alb-dns-name>`. To enable TLS, set `domain_name` and `route53_zone_id`
> (or bring your own `acm_certificate_arn`) — see [Custom domain & HTTPS](#custom-domain--https) below.

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
make terraform-bootstrap PREFIX=YOURNAME
```

Or run the underlying script directly: `./scripts/terraform-bootstrap-state.sh YOURNAME us-east-2`.

Edit `devops/terraform/environments/dev/backend.tf` and replace
`CHANGEME-headstart-tfstate` with your bucket name (`YOURNAME-headstart-tfstate`).
Do the same in `environments/prod/backend.tf` when you add production.

> **Tip:** `make aws-first-deploy` passes the bucket via `terraform init
> -backend-config`, so you can skip editing `backend.tf` on a first deploy.

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
terraform output app_url             # primary URL (HTTPS when configured)
terraform output alb_dns_name        # ALB DNS name (always available)
terraform output https_enabled       # true when TLS is active
terraform output ecs_cluster_name    # e.g. headstart-dev
terraform output ecr_repository_urls
```

ECS services will not become healthy until images exist in ECR (next step).

---

## 3. Build, push, and roll services

From the **repository root**, with Docker running:

```bash
eval "$(make aws-deploy-env)"
make deploy
```

`make aws-deploy-env` reads Terraform outputs and prints `AWS_REGION`, `ECR_REGISTRY`,
`ECS_CLUSTER`, and `ENVIRONMENT`. For production use `eval "$(make aws-deploy-env ENVIRONMENT=prod)"`.

Or set the variables manually:

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
3. Runs DB migrations as a one-off ECS task (`headstart-migrate`)
4. Forces a rolling deploy of `headstart-api`, `headstart-frontend`,
   `headstart-worker`, and `headstart-beat`

Verify rollout:

```bash
aws ecs describe-services \
  --cluster "$ECS_CLUSTER" \
  --services headstart-api headstart-frontend headstart-worker headstart-beat \
  --region "$AWS_REGION" \
  --query 'services[*].[serviceName,runningCount,desiredCount,deployments[0].rolloutState]' \
  --output table
```

Health check:

```bash
eval "$(make aws-deploy-env)"
curl "$APP_URL/api/v1/health"
```

Or with the raw ALB DNS name:

```bash
curl "http://$(cd devops/terraform/environments/dev && terraform output -raw alb_dns_name)/api/v1/health"
```

---

## 4. Use the app

Open the app URL in a browser (`terraform output app_url`):

- **UI:** `<app-url>/`
- **API docs:** `<app-url>/docs`

Without a custom domain, use `http://<alb-dns>/` as above.

There is no `make seed` on AWS. Continue with
[getting-started.md](getting-started.md) from **step 2** (create your account).
The first registered user becomes admin.

Before inviting public users, work through
[launch-checklist.md](launch-checklist.md) (domain, SMTP, legal pages, auto-apply
limits).

---

## Ongoing deploys

After infrastructure exists, ship code changes with:

```bash
eval "$(make aws-deploy-env)"          # or ENVIRONMENT=prod
make deploy
```

Or set `AWS_REGION`, `ECR_REGISTRY`, `ECS_CLUSTER`, and optional `ENVIRONMENT` manually.

Migrations run automatically on each deploy.

---

## Production (`prod` environment)

When ready for production:

1. Update `devops/terraform/environments/prod/backend.tf` with your state bucket.
2. `cd environments/prod` and run `terraform init && terraform apply` with the
   same `TF_VAR_*` secrets pattern.
3. Set `TF_VAR_cors_origins` to your real domain(s) — see
   `prod/terraform.tfvars.example`.
4. Deploy with `ENVIRONMENT=prod` and `ECS_CLUSTER=headstart-prod`.

`prod` uses larger instances, Multi-AZ RDS, and deletion protection on the
database.

---

## Custom domain & HTTPS

ACM cannot issue a certificate for the default `*.elb.amazonaws.com` hostname, so
HTTPS requires a domain you control.

**Recommended (Route53 + auto ACM):** add to `terraform.tfvars` or `TF_VAR_*`:

```hcl
domain_name       = "jobs.example.com"
route53_zone_id   = "Z0123456789ABCDEFGHIJ"   # hosted zone for example.com
# cors_origins defaults to https://jobs.example.com when domain_name is set
```

On `terraform apply`, Terraform will:

1. Request a DNS-validated ACM certificate
2. Add the ALB HTTPS listener on port 443 (TLS 1.2+)
3. Redirect HTTP → HTTPS on port 80
4. Create a Route53 alias `A` record pointing at the ALB
5. Set `CORS_ORIGINS` to `https://<domain_name>` unless you override `cors_origins`
6. Set `FRONTEND_BASE_URL` to the same public URL (password-reset and Stripe links)

### Transactional email (optional)

Set SMTP variables so password reset and the **email** notifier work from your
domain:

```hcl
smtp_host     = "email-smtp.us-east-2.amazonaws.com"
smtp_user     = "AKIA..."
# smtp_password via TF_VAR_smtp_password (stored in Secrets Manager)
# smtp_from   = "noreply@jobs.example.com"   # defaults to noreply@<domain_name>
```

Or export `TF_VAR_smtp_host`, `TF_VAR_smtp_user`, and `TF_VAR_smtp_password`
before `terraform apply` / `make aws-first-deploy`.

Verify SPF/DKIM with your provider. Full go-live steps:
[launch-checklist.md](launch-checklist.md).

**Bring your own certificate:** if the cert is already issued in the same region
as the ALB:

```hcl
domain_name           = "jobs.example.com"
route53_zone_id       = "Z0123456789ABCDEFGHIJ"   # optional: only for alias record
acm_certificate_arn   = "arn:aws:acm:us-east-2:123456789012:certificate/..."
```

If you set `acm_certificate_arn` without `route53_zone_id`, create the DNS alias
(or CNAME) to the ALB yourself.

Verify after apply:

```bash
terraform output https_enabled   # true
terraform output app_url           # https://jobs.example.com
curl "$(terraform output -raw app_url)/api/v1/health"
```

---

## CI/CD (CI active; deploy/terraform dormant)

All workflows live in `.github/workflows/`. The **CI** quality gate (`ci.yml`)
runs on every push and pull request — backend lint/type/tests and frontend
lint/type/tests/build, both gated at 100% coverage. **`deploy.yml`** is
manual-only (`workflow_dispatch`) and its job is guarded by
`if: vars.AWS_ROLE_ARN != ''`, so it stays dormant until you set that repo
variable; **`terraform.yml`** runs `fmt`/`validate` on `devops/terraform/**` PRs
and its credentialed `plan` step is gated on the same variable. Configure the AWS
OIDC role (`AWS_ROLE_ARN`) plus the application secrets (`JWT_SECRET`,
`CREDENTIALS_SECRET_KEY`, and the `TF_VAR_*` secrets) to activate them — no files
need to move.

---

## Troubleshooting

| Symptom | Likely cause / fix |
| ------- | ------------------ |
| ECS tasks stuck `PENDING` | Images not in ECR yet — run `make deploy` |
| `make deploy` fails on ECR login | `aws sts get-caller-identity` or region mismatch |
| Health check fails | Migrations not finished; check CloudWatch log group `/ecs/headstart-dev` |
| 401 / login loops in UI | API not reachable; confirm ALB routes `/api/*` to the API target group |
| No job notifications | Same as local — ntfy topic mismatch; see [getting-started.md](getting-started.md) |
| `terraform apply` state lock | Another apply in progress, or stale DynamoDB lock row |

Operational debugging (logs, pipeline) is covered in [runbook.md](runbook.md).
