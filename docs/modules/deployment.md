# Module: Deployment

**Path:** `devops/terraform/`

The same container images run locally (Docker Compose) and on AWS (ECS Fargate).
Local development never depends on anything in `devops/`.

## Backend dependency lockfiles

Runtime (and optional `dev` / `playwright`) dependencies are pinned with hashes
in `backend/requirements.txt`, `requirements-dev.txt`, and
`requirements-playwright.txt` (pip-tools; see
[ADR-0012](../adr/0012-backend-dependency-lockfiles.md)). The Dockerfile and CI
install with `pip install --require-hashes -r …`, then install the local package
with `--no-deps`. Regenerate via `just lock-backend` after editing
`backend/pyproject.toml` dependency floors.

**Floors must match tested majors (XCT-23).** `pyproject.toml` `>=` floors are
the human-readable support contract. Keep them aligned with the majors already
pinned in the lockfiles (and exercised by CI) — for example `celery>=5.6`,
`redis>=6.0`, `httpx>=0.28`, `cryptography>=49.0`, `stripe>=15.0`. Do not leave
floors on older majors the suite never runs against.

**Dependency CVE scanning (OPS-19).** CI runs `just audit-backend` after the
dev install (`pip-audit --disable-pip` against the three hashed lockfiles).
`pip-audit` is a `[dev]` extra. Dependabot watches `/backend` weekly alongside
the frontend npm ecosystem. Locally: `just audit-backend` (needs
`./scripts/install-backend.sh --dev`).

## AWS topology

```mermaid
flowchart LR
  internet((Internet)) --> alb[ALB]
  alb --> feSvc["ECS service: frontend"]
  alb --> apiSvc["ECS service: api"]
  apiSvc --> rds[("RDS Postgres")]
  apiSvc --> redis[("ElastiCache Redis")]
  beatSvc["ECS service: beat"] --> redis
  workerSvc["ECS service: worker"] --> redis
  workerSvc --> rds
  workerSvc --> internet
```

## Terraform layout

```
devops/terraform/
├── modules/
│   ├── network/   # VPC, subnets, security groups
│   ├── ecr/       # image repositories
│   ├── rds/       # Postgres
│   ├── redis/     # ElastiCache
│   ├── acm/       # DNS-validated TLS certificates (optional)
│   ├── alb/       # load balancer, listeners, target groups, access logs, WAF
│   ├── ecs/       # cluster, task defs + services (api, frontend, worker, beat)
│   ├── iam/       # task execution + task roles
│   └── secrets/   # Secrets Manager / SSM params
└── environments/
    ├── beta/
    └── prod/
```

State is remote: S3 bucket + DynamoDB lock table. Each environment's
`backend.tf` is a **partial** config (state `key`, region, lock table,
encryption); the bucket is supplied at `terraform init` via
`-backend-config` / `backend.hcl` so a real bucket name is never committed
(OPS-29). Secrets are stored in Secrets Manager / SSM and injected into ECS
task definitions — never in Terraform variables committed to git. Core apply
secrets (`db_password`, `jwt_secret`, `credentials_secret_key`) are supplied
only via `TF_VAR_*` env vars; beta/prod `terraform.tfvars.example` files no
longer show inline assignments for them so operators are not primed to paste
real secrets into a local `terraform.tfvars` (OPS-33).

## HTTPS (optional)

By default the ALB serves HTTP on port 80 using its AWS-assigned DNS name. To
terminate TLS:

- Set `domain_name` + `route53_zone_id` in the environment module to provision
  ACM (DNS validation), an HTTPS listener on 443, HTTP→HTTPS redirect, and a
  Route53 alias to the ALB.
- Or pass a pre-validated `acm_certificate_arn` in the same region as the ALB.

`app_url`, `CORS_ORIGINS`, and `FRONTEND_BASE_URL` default to `https://<domain>`
when HTTPS is enabled. `AUTH_COOKIE_SECURE` is derived the same way (`true` when
`https_enabled`, otherwise `false`) so the refresh cookie is not dropped on the
default HTTP ALB. Outside `local`/`test`, the API also refuses to boot when
`AUTH_COOKIE_SECURE=true` is paired with a non-`https` `FRONTEND_BASE_URL`, or
when `AUTH_COOKIE_SAMESITE=none` is set without Secure (AUT-13). Optional
`smtp_*` variables configure transactional email (`SMTP_PASSWORD` in Secrets
Manager). `ntfy_default_topic` is **required** (no Terraform default): ntfy.sh
topics are public by name, so beta/prod reject empty or `change-me` placeholders
and the app refuses the same guessable default outside `local`/`test` (OPS-16).
See [deploying-to-aws.md](../deploying-to-aws.md#custom-domain--https) and
[launch-checklist.md](../launch-checklist.md).

## Worker sizing (Playwright)

The worker service uses a separate container image (`headstart-backend-worker`)
with Chromium pre-installed. Default Fargate sizing is **1024 CPU / 2048 MiB**
(vs **256 / 512** for api, beat, and frontend). Override via stack module vars
`worker_cpu` and `worker_memory` in `environments/<env>/main.tf`.

## Distinct VPC CIDRs (OPS-30)

Beta and prod must not share the same private address space. Each environment's
`main.tf` sets `vpc_cidr` / subnet CIDRs explicitly:

| Environment | VPC CIDR | Public subnets | Private subnets |
| ----------- | -------- | -------------- | --------------- |
| beta | `10.20.0.0/16` | `10.20.0.0/24`, `10.20.1.0/24` | `10.20.10.0/24`, `10.20.11.0/24` |
| prod | `10.30.0.0/16` | `10.30.0.0/24`, `10.30.1.0/24` | `10.30.10.0/24`, `10.30.11.0/24` |

Stack module defaults stay on the beta range for backwards-compatible local
module calls; env wrappers own the real pin. `TRUSTED_PROXY_CIDRS` follows
`var.vpc_cidr`, so ALB-trusted XFF stays aligned with each env's VPC.

**Existing prod stacks** that already applied the old shared `10.20.0.0/16`
will see a VPC replacement on the next apply — plan carefully (or leave the
live CIDR and only use `10.30` for greenfield prod).

## AWS account pin (OPS-31)

Beta and prod providers set `allowed_account_ids = [var.aws_account_id]`.
`aws_account_id` is **required** (no default) and must be a 12-digit AWS
account ID. A plan/apply with ambient credentials for a different account
fails at provider initialization instead of provisioning into the wrong
account. Prefer:

```bash
export TF_VAR_aws_account_id="$(aws sts get-caller-identity --query Account --output text)"
```

`scripts/aws-first-deploy.sh` resolves the caller account when unset and
persists it to `.aws-first-deploy-secrets.env` so later runs keep the pin.

## Prod resilience knobs (OPS-05 / OPS-08 / OPS-10)

`environments/prod/main.tf` raises durability beyond the stack defaults that
`beta` keeps:

| Knob | Stack default (beta) | Prod |
| ---- | -------------------- | ---- |
| `db_multi_az` / `db_deletion_protection` | false | true |
| `alb_deletion_protection` | false | true |
| `db_backup_retention_days` | 7 | 30 |
| `log_retention_days` (ECS CloudWatch) | 30 | 90 |
| `redis_automatic_failover` | false (1-node replication group) | true (Multi-AZ, 2 nodes) |

`backup_retention_days` and `log_retention_days` are plumbed through the stack
module into `rds` / `ecs`. Redis is always an
`aws_elasticache_replication_group` (required for in-transit encryption) with
`transit_encryption_enabled`, `at_rest_encryption_enabled` (AWS-managed KMS by
default; optional `kms_key_id`), and an AUTH token from `random_password` stored
in Secrets Manager as `REDIS_PASSWORD`. ECS tasks get `REDIS_TLS=true` and the
password secret so Celery builds `rediss://` broker/result URLs with
`ssl_cert_reqs=required` (OPS-10).
Enabling encryption/AUTH on an existing unencrypted broker replaces the
resource (brief Celery downtime on apply). Prod also requires an explicit
immutable `image_tag` (git SHA): there is no `"latest"` default, and Terraform
rejects `latest` so a task recycle cannot silently pull a different build
(OPS-07). ECR repositories set `image_tag_mutability = "IMMUTABLE"` so a
re-push cannot overwrite a tag that task definitions still reference (OPS-09).
Ongoing rolls still retarget task defs via `deploy.sh` / `IMAGE_TAG`.

### ALB hardening (OPS-08)

Every environment's ALB (beta and prod) enables:

- `drop_invalid_header_fields = true` (reject request-smuggling via malformed headers)
- S3 access logs (`{name}-alb-access-logs-{account}`) with a 90-day lifecycle
- A regional WAFv2 web ACL (AWS Managed Common + Known Bad Inputs rule groups)

Prod additionally sets `alb_deletion_protection = true` so a fat-finger
`terraform destroy` cannot delete the public entrypoint. Beta keeps deletion
protection off so throwaway stacks can tear down cleanly (the access-logs
bucket uses `force_destroy` when deletion protection is off).

### Tasks SG from ALB (OPS-14)

The shared ECS tasks security group accepts ingress from the ALB SG only on the
two target-group ports: **8080** (frontend, unprivileged nginx) and **8000**
(api). A prior `0–65535` rule would also have exposed the worker metrics port
(`9090`) to any member of the ALB SG. Worker/beat have no ALB targets; scrape
them from a dedicated Prometheus/CloudWatch agent security group, not via the
ALB rule.

## Observability

Prometheus metrics are exposed from two scrape targets:

- **API** service: `GET /metrics` on port 8000 (synchronous pipeline runs).
- **Worker** service: `GET /metrics` on `METRICS_PORT` (default 9090).

See [modules/metrics.md](../modules/metrics.md) for metric names, PromQL examples,
and `METRICS_TOKEN` Bearer auth (honored by both API and worker scrape targets).
Terraform always stores a generated `METRICS_TOKEN` in Secrets Manager and injects
it into ECS tasks (OPS-54), so AWS scrapes must send `Authorization: Bearer`.
On AWS, open worker `:9090` from your scraper security group (not the ALB SG;
see OPS-14 above) and scrape with Prometheus or the CloudWatch agent.

## Deploy flow

`just deploy` (→ `scripts/deploy.sh`). Load deploy env vars with
`eval "$(just aws-deploy-env)"` (reads Terraform outputs for `ECR_REGISTRY`,
`ECS_CLUSTER`, `APP_URL`, etc.).

**First-time deploy:** `just aws-first-deploy PREFIX=yourname` chains state
bootstrap, `terraform apply`, and `just deploy` — see
[deploying-to-aws.md](../deploying-to-aws.md#quick-start-one-command).

1. Build images (`scripts/build-images.sh`): lean `headstart-backend` (api/beat)
   and `headstart-backend-worker` (Playwright + Chromium).
2. Push to ECR under tag `IMAGE_TAG` (git short SHA by default; CI uses the full
   commit SHA).
3. Resolve each pushed image's ECR content digest (`describe-images` →
   `imageDigest`) for `headstart-backend`, `headstart-backend-worker`, and
   `headstart-frontend`.
4. Register a new `headstart-migrate` task-definition revision whose container
   image is pinned to `:{IMAGE_TAG}@{sha256:…}` (not tag alone), then run
   migrations as a one-off ECS task. `deploy.sh` waits for the task to stop and
   requires every container `exitCode == 0` before continuing — a failed or
   still-running migration aborts the deploy so new app images never roll
   against a bad schema (OPS-17).
5. For each long-running service (`api`, `frontend`, `worker`, `beat`), register
   a new task-definition revision pinned to the same `tag@digest` (via
   `python -m app.cli.ecs_task_def retarget --image-digest …`) and
   `update-service --task-definition <new-arn> --force-new-deployment`.

ECS services use `lifecycle { ignore_changes = [task_definition] }` so Terraform
keeps the initial wiring while `deploy.sh` owns the image pin at roll time.
Force-new-deployment alone is not enough when the task def still points at a
tag the build never re-pushes (historically Terraform's `image_tag = "latest"`;
prod now requires an immutable SHA pin — OPS-07). `deploy.sh` registers a new
revision pinned to `IMAGE_TAG` before rolling (OPS-01), and further pins that
revision to the ECR content digest resolved after push (OPS-64) so the rolled
task cannot pull a different manifest than this pipeline built — even if a tag
were ever mutable again.

All workflows live in `.github/workflows/`. The CI quality gate (`ci.yml`) runs
on push/PR: backend `just lint` (ruff + black + LOC), `just typecheck`,
`just test`, `just test --scripts` (shell syntax), and `just audit-backend`
(`pip-audit` on the hashed lockfiles, OPS-19); frontend `just lint`
(eslint + prettier `--check`), `just typecheck`, `just test`, build, and
`just audit-frontend` (`npm audit --audit-level=high`, FRO-12). Every
third-party `uses:` is pinned to a full commit SHA with a version comment
(OPS-20) so a re-pointed `@vN` tag cannot silently change the job; Dependabot
opens weekly PRs for those SHAs, for `frontend/package-lock.json`, and for
backend pip (`.github/dependabot.yml`). On push failures, a `notify` job posts
to Slack when `secrets.SLACK_WEBHOOK_URL` is set — the webhook is mapped at
**job** level so the step `if: env.SLACK_WEBHOOK_URL != ''` can see it
(OPS-21; step-level `env` is not available to that same step's `if`). Local
pre-commit is a **fast subset** of that gate (whitespace/yaml, ruff/black,
eslint, prettier, LOC, shell validation) — types, tests, coverage, and
dependency audits stay in `just check` / CI. The `frontend-lint` hook runs
`npx eslint . --max-warnings=0` (same as `npm run lint`) so ESLint always
receives an explicit path — without one, ESLint 8 scans zero files and exits
0 (OPS-03). LOC, shell validation, and prettier are enforced in both
pre-commit and CI (OPS-04). `deploy.yml` (manual `workflow_dispatch`) and
`terraform.yml`'s credentialed `plan` step are guarded on
`vars.AWS_ROLE_ARN`, so they stay dormant until AWS is configured; once set,
`terraform plan` runs on PRs and `deploy` runs `terraform apply` +
`just deploy` on demand.

## First-time setup

See **[deploying-to-aws.md](../deploying-to-aws.md)** for the full walkthrough
(prerequisites, state bootstrap, `terraform apply`, `just deploy`, verification).

Summary:

1. Bootstrap S3 state + DynamoDB lock, then
   `terraform init -backend-config=…` (bucket not in committed `backend.tf`;
   OPS-29).
2. `terraform apply` in `environments/beta` (or `prod`).
3. `just deploy` with `ECR_REGISTRY` and `ECS_CLUSTER` set.
4. Optional: activate the deploy/terraform workflows by setting the `AWS_ROLE_ARN`
   repo variable and the AWS/GitHub secrets (the workflow files are already in place).
