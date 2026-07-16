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
just aws-first-deploy PREFIX=your-unique-name
```

This single command:

1. Creates the remote Terraform state bucket + DynamoDB lock table (if missing)
2. Generates application secrets and saves them to `.aws-first-deploy-secrets.env`
   (gitignored — back them up)
3. Runs `terraform init` (with `-backend-config` for the state bucket — OPS-29)
   and `terraform apply`
4. Builds container images, pushes to ECR, runs migrations, and rolls ECS services

Add `YES=1` to skip the terraform confirmation prompt (useful in automation).
Add `SKIP_DEPLOY=1` to provision infrastructure only (no Docker image push).

Optional HTTPS on **beta** during first deploy (Route53 hosted zone required).
**Prod** always needs these (or `ACM_CERTIFICATE_ARN`) — OPS-36:

```bash
just aws-first-deploy PREFIX=yourname \
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

- VPC, subnets, security groups, VPC flow logs → CloudWatch (OPS-41)
- Application Load Balancer (public entrypoint; HTTP allowed on **beta**,
  **prod** requires HTTPS — OPS-36)
- ECS Fargate cluster with services: `api`, `frontend`, `worker`, `beat`
- RDS Postgres (CMK encryption, IAM DB auth, Performance Insights, Postgres
  log exports, Enhanced Monitoring — OPS-43) + ElastiCache Redis
- ECR repositories for backend, backend-worker (Playwright), and frontend images
  (tags are **immutable** — re-pushing the same tag fails; use a new git SHA —
  OPS-09)
- Secrets Manager entries for `POSTGRES_PASSWORD`, `JWT_SECRET`,
  `CREDENTIALS_SECRET_KEY` (and Redis / metrics / optional SMTP) encrypted with
  a customer-managed KMS key and an explicit recovery window (OPS-51)

Default region is **`us-east-2`**. Use the **`beta`** environment first (cheaper);
**`prod`** adds Multi-AZ RDS and deletion protection on RDS and the ALB. Both
environments enable ALB access logs, `drop_invalid_header_fields`, and a
regional WAFv2 ACL (OPS-08), VPC flow logs to CloudWatch (OPS-41), and the
RDS datastore hardening above (OPS-43).

> **Cost:** even `beta` runs an ALB, four Fargate tasks, RDS, and Redis — expect
> ongoing monthly charges, not a free-tier-only stack.

> **HTTPS:** **beta** without a custom domain serves **HTTP on port 80** at
> `http://<alb-dns-name>`. **Prod** requires TLS: set `domain_name` and
> `route53_zone_id` (or `acm_certificate_arn`) or Terraform plan/apply fails
> (`check "prod_requires_https"`, OPS-36) — see
> [Custom domain & HTTPS](#custom-domain--https) below.
> On HTTP-only beta deploys Terraform sets `AUTH_COOKIE_SECURE=false` (derived from
> `https_enabled`) so the httpOnly refresh cookie is stored; with HTTPS it stays
> `true`. Do not override that coupling unless you terminate TLS elsewhere.

---

## Prerequisites

On the machine that will run Terraform and build images:

| Tool | Install |
| ---- | ------- |
| AWS CLI v2 | [AWS install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| Terraform | [HashiCorp install guide](https://developer.hashicorp.com/terraform/install) |
| Docker | engine + `docker compose` plugin |
| `just`, `git`, `openssl` | `sudo apt install -y just`; git/openssl usually preinstalled |

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
just terraform-bootstrap PREFIX=YOURNAME
```

Or run the underlying script directly: `./scripts/terraform-bootstrap-state.sh YOURNAME us-east-2`.

Committed `backend.tf` files omit the state bucket (OPS-29). After bootstrap,
pass it at init — copy `backend.hcl.example` → `backend.hcl` (gitignored) and
set `bucket = "YOURNAME-headstart-tfstate"`, then
`terraform init -backend-config=backend.hcl`. Repeat for `environments/prod`
when you add production.

> **Tip:** `just aws-first-deploy` passes the bucket via `terraform init
> -backend-config`, so you can skip creating `backend.hcl` on a first deploy.

---

## 2. Provision infrastructure

```bash
cd devops/terraform/environments/beta

# Save these somewhere safe — you cannot recover them from Terraform output.
export TF_VAR_db_password="$(openssl rand -base64 24)"
export TF_VAR_jwt_secret="$(openssl rand -hex 32)"
export TF_VAR_credentials_secret_key="$(openssl rand -hex 32)"

# Required: pin the AWS account this env may target (OPS-31). Wrong ambient
# credentials then fail at provider init instead of applying into another account.
export TF_VAR_aws_account_id="$(aws sts get-caller-identity --query Account --output text)"

# Required: unguessable default ntfy topic (ntfy.sh topics are public by name).
# Terraform rejects empty / change-me placeholders (OPS-16).
export TF_VAR_ntfy_default_topic="jobs-$(openssl rand -hex 8)"

cp backend.hcl.example backend.hcl
# edit: bucket = "YOURNAME-headstart-tfstate"
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

Secrets are written to **AWS Secrets Manager** and injected into ECS tasks at
runtime. Never commit them to git. Keep `db_password` / `jwt_secret` /
`credentials_secret_key` in the shell as `TF_VAR_*` (OPS-33) — do not paste them
into `terraform.tfvars`. Non-secret knobs may use a local `terraform.tfvars`
(gitignored); see `terraform.tfvars.example` in the same directory.

Note the outputs:

```bash
terraform output app_url             # primary URL (HTTPS when configured)
terraform output alb_dns_name        # ALB DNS name (always available)
terraform output https_enabled       # true when TLS is active
terraform output ecs_cluster_name    # e.g. headstart-beta
terraform output ecr_repository_urls
```

ECS services will not become healthy until images exist in ECR (next step).

---

## 3. Build, push, and roll services

From the **repository root**, with Docker running:

```bash
eval "$(just aws-deploy-env)"
just deploy
```

`just aws-deploy-env` reads Terraform outputs and prints shell-safe
`export` lines (`printf %q`, OPS-62) for `AWS_REGION`, `ECR_REGISTRY`,
`ECS_CLUSTER`, `APP_URL`, and `ENVIRONMENT`. For production use
`eval "$(just aws-deploy-env ENVIRONMENT=prod)"`.

Or set the variables manually:

```bash
export AWS_REGION=us-east-2
export ENVIRONMENT=beta
export ECR_REGISTRY="$(aws sts get-caller-identity --query Account --output text).dkr.ecr.${AWS_REGION}.amazonaws.com"
export ECS_CLUSTER="$(cd devops/terraform/environments/beta && terraform output -raw ecs_cluster_name)"
just deploy
```

`just deploy` runs `scripts/deploy.sh`, which:

1. Builds backend images (`scripts/build-images.sh --push`): lean API/beat image
   plus the Playwright-enabled worker image, and the frontend image
2. Pushes them to ECR (tag = current git short SHA, or `latest` if not in git).
   ECR tags are immutable (OPS-09), so re-pushing an existing tag fails — use a
   new commit SHA (or a unique `IMAGE_TAG`) for each build.
3. Resolves each pushed image's ECR content digest and registers task definitions
   with `:{IMAGE_TAG}@{sha256:…}` so the roll is pinned to the exact manifest
   this pipeline pushed (OPS-64), not only the tag string
4. Registers a new `headstart-migrate` task-definition revision with that
   digest pin, then runs DB migrations as a one-off ECS task, waits until the
   task stops, and aborts the deploy unless every container exits 0 (OPS-17)
5. Registers a new digest-pinned task-definition revision per long-running
   service (`headstart-api`, `headstart-frontend`, `headstart-worker`,
   `headstart-beat`), then rolls each service onto that revision

The retarget step matters: if a task definition still pointed at a floating
tag such as `latest` (which the build does not re-push), a bare
`--force-new-deployment` would keep serving the old image. Updating the service
with `--task-definition` (not only `--force-new-deployment`) is what makes the
deployed image match the just-built tag (OPS-01). Pinning `@sha256:…` closes the
remaining build→deploy provenance gap if a tag ever pointed at a different
manifest than the one this run pushed (OPS-64). Prod Terraform also requires
an immutable `image_tag` (git SHA) up front and rejects `latest` (OPS-07).
ECR repositories themselves reject tag overwrite (`image_tag_mutability =
"IMMUTABLE"`, OPS-09), so a compromised or accidental re-push cannot replace
the digest behind a tag still referenced by task definitions.
The migrate await matters too: without it, a failed or still-running schema
change would let new app images roll and serve 500s until noticed.

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
eval "$(just aws-deploy-env)"
curl "$APP_URL/api/v1/health"
```

Or with the raw ALB DNS name:

```bash
curl "http://$(cd devops/terraform/environments/beta && terraform output -raw alb_dns_name)/api/v1/health"
```

---

## 4. Use the app

Open the app URL in a browser (`terraform output app_url`):

- **UI:** `<app-url>/`
- **API health:** `<app-url>/api/v1/health`

Interactive OpenAPI docs (`/docs`) are disabled in deployed environments
(AUT-25); use a local `just dev` stack to browse the schema.

Without a custom domain, use `http://<alb-dns>/` as above.

There is no `just seed` on AWS. Continue with
[getting-started.md](getting-started.md) from **step 2** (create your account).
The first registered user becomes admin.

Before inviting public users, work through
[launch-checklist.md](launch-checklist.md) (domain, SMTP, legal pages, auto-apply
limits).

---

## Ongoing deploys

After infrastructure exists, ship code changes with:

```bash
eval "$(just aws-deploy-env)"          # or ENVIRONMENT=prod
just deploy
```

Or set `AWS_REGION`, `ECR_REGISTRY`, `ECS_CLUSTER`, and optional `ENVIRONMENT` manually.

Migrations run automatically on each deploy.

---

## Production (`prod` environment)

When ready for production:

1. Copy `environments/prod/backend.hcl.example` → `backend.hcl` and set your
   state bucket (OPS-29 — do not commit the bucket into `backend.tf`).
2. `cd environments/prod` and run
   `terraform init -backend-config=backend.hcl && terraform apply` with the
   same `TF_VAR_*` secrets pattern. Set `TF_VAR_aws_account_id` to the 12-digit
   production account (OPS-31 — provider `allowed_account_ids` rejects a wrong
   ambient credential). Prod also requires an immutable image pin
   (no `"latest"` default; Terraform rejects `latest` — OPS-07):
   `export TF_VAR_image_tag="$(git rev-parse --short HEAD)"`.
3. Set `TF_VAR_cors_origins` to your real domain(s) — see
   `prod/terraform.tfvars.example`.
4. Deploy with `ENVIRONMENT=prod` and `ECS_CLUSTER=headstart-prod`.

`prod` uses larger instances, Multi-AZ RDS, and deletion protection on the
database and ALB. ALB access logs + WAF apply in beta and prod (OPS-08).

---

## Custom domain & HTTPS

ACM cannot issue a certificate for the default `*.elb.amazonaws.com` hostname, so
HTTPS requires a domain you control. **Prod requires HTTPS** — without
`domain_name` + `route53_zone_id` (or `acm_certificate_arn`), the stack check
`prod_requires_https` fails plan/apply so the ALB cannot forward auth traffic
over plaintext HTTP (OPS-36). Beta may still use the HTTP ALB DNS name.

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
7. Set `AUTH_COOKIE_SECURE=true` (HTTP-only ALB deploys keep it `false` so the
   refresh cookie is not dropped by the browser)

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
before `terraform apply` / `just aws-first-deploy`.

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
runs on every push and pull request via the same `just check` / `scripts/check.sh`
entrypoints used locally (OPS-22) — backend lint (including the LOC cap) /
type / tests, shell-script validation, and frontend lint (eslint + prettier
`--check`) / type / tests / `just build-frontend`, both coverage-gated at 100%.
Third-party GitHub Actions are pinned to full commit SHAs (OPS-20); Dependabot
bumps those SHAs weekly alongside frontend npm and backend pip. Local
pre-commit is a fast subset (formatters, eslint, prettier, LOC, shell).
**`deploy.yml`** is
manual-only (`workflow_dispatch`) and its job is guarded by
`vars.AWS_ROLE_ARN != ''` **and** `github.ref` being `refs/heads/main` or
`refs/heads/master` (OPS-23), so it stays dormant until you set that repo
variable and only assumes the role from protected default-branch refs;
**`terraform.yml`** runs `fmt`/`validate` on `devops/terraform/**` PRs with
**no** secrets and **no** AWS assume (OPS-24). Its credentialed `plan` job is
manual-only (`workflow_dispatch`), gated on `vars.AWS_ROLE_ARN`,
`vars.TF_STATE_BUCKET`, default-branch refs (`main`/`master`), and the
`beta`/`prod` GitHub Environment — same trust model as deploy. Configure the
AWS OIDC role (`AWS_ROLE_ARN`), state bucket (`TF_STATE_BUCKET`), plus the
`TF_VAR_*` secrets to activate plan; no files need to move.

When creating the deploy/plan IAM role trust policy, pin the GitHub OIDC `sub`
(and `aud`) claims — for example
`repo:<owner>/<repo>:ref:refs/heads/main` with audience `sts.amazonaws.com`.
Do not use `repo:<owner>/<repo>:*`. Enable required reviewers on the `beta`
and `prod` GitHub Environments, and keep branch protection on `main`/`master`.
Deploy sets `role-session-name: headstart-deploy-<run_id>`; terraform plan sets
`headstart-tf-plan-<run_id>` so CloudTrail rows identify the Actions run.

---

## Troubleshooting

| Symptom | Likely cause / fix |
| ------- | ------------------ |
| ECS tasks stuck `PENDING` | Images not in ECR yet — run `just deploy` |
| `just deploy` fails on ECR login | `aws sts get-caller-identity` or region mismatch |
| Health check fails | Migrations not finished; check CloudWatch log group `/ecs/headstart-beta` |
| 401 / login loops in UI | API not reachable; confirm ALB routes `/api/*` to the API target group |
| No job notifications | Same as local — ntfy topic mismatch; see [getting-started.md](getting-started.md) |
| `terraform apply` state lock | Another apply in progress, or stale DynamoDB lock row |

Operational debugging (logs, pipeline) is covered in [runbook.md](runbook.md).
