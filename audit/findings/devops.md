# DevOps — Terraform/IaC, Docker, scripts, CI/CD

This area covers the deployment and infrastructure surface of the repo: the AWS Terraform stack (`devops/terraform/`), the `Dockerfile`/`docker-compose.yml` container definitions, the shell scripts under `scripts/`, and the GitHub Actions workflows. The headline finding is a **build/release integrity bug**: `make deploy` pushes a git-SHA-tagged image but only force-new-deployments services whose task definitions pin an image tag the build never re-pushes, so new code silently never ships (OPS-01). The CI/CD quality gate advertised in `AGENTS.md` runs: `ci.yml` enforces lint/type/test/coverage (including LOC via `just lint --backend`, shell via `just test --scripts`, and prettier via `just lint --frontend`) on push/PR, and pre-commit is a fast subset covering ruff/black/eslint/prettier/LOC/shell (OPS-03, OPS-04 closed). The `deploy.yml`/`terraform.yml` workflows are **dormant** — `deploy.yml` is manual-only (`workflow_dispatch`) and guarded on `vars.AWS_ROLE_ARN`, and `terraform.yml`'s `plan` step is guarded on the same variable — so nothing AWS-touching runs until that variable/secrets are configured (OPS-23, OPS-24). The remainder is a broad, mostly low-severity Terraform hardening backlog: Redis broker without encryption/auth, mutable ECR tags, over-broad security groups, a public ntfy default topic, missing VPC flow logs / access logs / WAF, and various KMS/observability/HA gaps.

**Summary:** 0 critical · 1 high · 15 medium · 21 low (after merging duplicate records; 66 raw findings consolidated to 37).

---

<a id="ops-01"></a>
### OPS-01 — deploy.sh redeploys task defs pinned to a tag never re-pushed by the build
🟠 **HIGH** · 🐞 bug · Status: ✅ done · Confidence: high (5/5 verifiers) · Effort: M · WS36

**Locations:** `scripts/deploy.sh:33` (`deploy loop`); plus `scripts/build-images.sh:39`, `devops/terraform/modules/ecs/main.tf:7`, `devops/terraform/environments/prod/terraform.tfvars.example:7`.

**Evidence.** `deploy.sh` sets `IMAGE_TAG=<git-sha>`, pushes `headstart-<svc>:<sha>`, then runs `update-service --force-new-deployment` with no task-definition update. The task definitions resolve their image as `${repo}:${var.image_tag}`, and the prod tfvars pin `image_tag = "latest"`. `build-images.sh` pushes only `:${IMAGE_TAG}` (the SHA) and never re-pushes `:latest`, so the tag the running task def points at is never refreshed.

**Failure scenario.** `make deploy` reports success, but ECS re-pulls the task def's pinned tag (`latest`), which was never re-pushed. Services roll back to the OLD image; new code and fixes silently never reach production.

**Suggested fix.** Register a new task-definition revision pinned to the freshly pushed tag (or additionally push and repin `:latest`) before force-new-deployment, so the deployed tag equals the built tag.

**Verification.** Confirmed 5/5 adversarial verifiers. deploy.sh pushes `:<git-sha>` and only force-new-deployments; task defs pin `${var.image_tag}="latest"` which build-images.sh never pushes, so ECS re-pulls the stale tag and new code silently never ships.

---

<a id="ops-03"></a>
### OPS-03 — Pre-commit frontend-lint runs eslint with no path: lints 0 files, always passes
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done · Confidence: certain (5/5 verifiers) · Effort: XS · WS37

**Update (2026-07-10).** Fixed: pre-commit `frontend-lint` runs
`npx eslint . --max-warnings=0` (same as `npm run lint`) and is renamed to
`frontend eslint` so ESLint always receives an explicit path. Without a path,
ESLint 8 scans zero files and exits 0 —
[PR](https://github.com/davidcristian/HeadStart/pull/72).

**Locations:** `.pre-commit-config.yaml:38` (`frontend-lint hook`); plus `.pre-commit-config.yaml:36` (hook name label).

**Note:** Merged with OPS-26 (frontend-lint hook mislabeled "changed files"), which is the same hook and the same root cause.

**Evidence.** The hook is `entry: bash -c 'cd frontend && npx eslint --max-warnings=0'` with `pass_filenames: false` and no path argument. ESLint 8 (flat-less `.eslintrc.cjs`) given no path lints nothing. Reproduced: with a real `no-unused-vars` error in `src/*.tsx`, `npx eslint --max-warnings=0` exits 0, while `eslint .` (the npm `lint` script) exits 1 and reports it. As a secondary defect, the hook is named "frontend eslint (changed files)" but with `pass_filenames: false` it would (if given a path) lint the whole project, not the changed files — the label is doubly misleading.

**Failure scenario.** A dev commits frontend TypeScript with lint errors; the only frontend pre-commit gate silently passes because it scans zero files. Bad code lands and nothing catches it locally at commit time.

**Suggested fix.** Pass changed filenames (`pass_filenames: true`) or lint an explicit path (`npx eslint . --max-warnings=0`), matching the npm `lint` script, and rename the hook to reflect its real scope.

**Verification.** Confirmed 5/5 adversarial verifiers. Reproduced: `npx eslint --max-warnings=0` (no path) exits 0 even with a real error, while `eslint .` exits 1; `pass_filenames: false` means the hook scans nothing, with no `.github` CI backstop.

---

<a id="ops-04"></a>
### OPS-04 — Claimed gates partially unenforced: ci.yml omits LOC/shell/prettier, pre-commit omits them too
🟡 **MEDIUM** · 🧪 test · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/73)) · Confidence: high (3/3 verifiers) · Effort: S · WS37

**Update (2026-07-10).** Fixed: `just lint --frontend` / CI run
`prettier --check`; pre-commit adds `frontend-prettier`, `check-loc`, and
`validate-shell-scripts` hooks; the pre-commit header now describes a fast
subset of CI (LOC and shell were already on the CI path via
`just lint --backend` / `just test --scripts`).

**Locations:** `.pre-commit-config.yaml:2` (`repos` / header comment); plus `scripts/lint.sh:18`, `scripts/typecheck.sh:6`, `scripts/validate-shell-scripts.sh:1`.

**Note:** Merged with OPS-25 (pre-commit claims to mirror CI but omits mypy/tsc/tests/coverage/LOC/shell); same defect, different severity vote.

**Evidence.** The pre-commit config header claims the hooks "mirror the CI quality gate." ci.yml runs ruff/black/mypy/pytest+coverage and eslint/tsc/vitest+coverage/build server-side, but neither ci.yml nor pre-commit runs `check_loc.sh` (the 300-line cap), `validate-shell-scripts.sh`, or `prettier --check`; pre-commit itself runs only whitespace/eof/yaml + ruff/black + the (broken) eslint hook, omitting the mypy/tsc/pytest/vitest/coverage that ci.yml covers.

**Failure scenario.** A PR that exceeds the 300-line cap, breaks a shell script, or violates Prettier formatting merges with zero automated enforcement — neither ci.yml nor pre-commit runs those checks; locally, a commit that breaks types or drops coverage below 100% passes pre-commit and is caught only later by ci.yml.

**Suggested fix.** Add `check_loc`, shell-validation, and `prettier --check` jobs to ci.yml (and/or wire them into pre-commit stages) so all AGENTS.md §5/§6 gates run automatically; alternatively reword the pre-commit header to state it is a fast subset of ci.yml.

**Verification.** Confirmed 3/3 adversarial verifiers. `.pre-commit-config` runs only ruff/black/eslint while the now-live `ci.yml` runs mypy/pytest/tsc/vitest+coverage but not check_loc/shell-validation/prettier — the "mirror the CI quality gate" header is inaccurate and the LOC/shell/prettier gates are not enforced automatically.

---

<a id="ops-05"></a>
### OPS-05 — Prod block sets RDS AZ/deletion-protection but omits backup + log retention and Redis HA
🟡 **MEDIUM** · 🔁 consistency · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/67)) · Confidence: high (3/3 verifiers) · Effort: M · WS36

**Update (2026-07-10).** Fixed: stack exposes `db_backup_retention_days` and `log_retention_days`; prod sets 30-day RDS backups, 90-day ECS CloudWatch retention, and `redis_automatic_failover` (Multi-AZ replication group). Also closes OPS-49.

**Locations:** `devops/terraform/environments/prod/main.tf:23` (`module.stack (prod knobs)`); plus `devops/terraform/modules/stack/variables.tf:123`, `devops/terraform/modules/stack/main.tf:116`, `devops/terraform/modules/rds/variables.tf:37`, `devops/terraform/modules/ecs/variables.tf:82`, `devops/terraform/modules/redis/main.tf:14`.

**Note:** Rollup of OPS-06 (the narrower "backup retention same as dev" record) into this superset finding covering backup retention, log retention, and Redis HA.

**Evidence.** The prod `module.stack` call overrides `db_multi_az`, `db_deletion_protection`, and instance sizing, but the stack module never exposes `backup_retention_days` (the `stack/main.tf` RDS block at l116 never passes it) or `log_retention_days`, so both envs inherit the RDS module default of 7 days (`rds/variables.tf:37`). Redis is hardcoded `num_cache_nodes = 1` with no failover. Prod therefore silently inherits dev defaults for backups, log retention, and cache HA.

**Failure scenario.** Prod keeps only 7 days of DB backups and default log retention with no tuning path; corruption or an accidental delete discovered more than 7 days later has no recoverable backup. Redis has no automatic failover, so a broker node loss stalls all Celery scheduling.

**Suggested fix.** Plumb `backup_retention_days` and `log_retention_days` through the stack module and set higher prod values (e.g. 30-day backups); add a Redis replication/failover option for prod.

**Verification.** Confirmed 3/3 adversarial verifiers. No `backup_retention_days`/`log_retention_days` is plumbed through the stack, and `redis/main.tf:14` hardcodes `num_cache_nodes=1` (no failover). This is the rollup superset of the narrower backup-only record.

---

<a id="ops-07"></a>
### OPS-07 — Prod deploys mutable image_tag "latest" — no immutable pin or rollback
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: S · WS36

**Update (2026-07-10).** Fixed: prod `image_tag` has no default, validates
non-empty and rejects `latest`, and `terraform.tfvars.example` documents a git
SHA pin. `aws-first-deploy.sh` sets `TF_VAR_image_tag` from the short SHA when
`ENVIRONMENT=prod`. ECR tag mutability remains tracked as [OPS-09](#ops-09).

**Locations:** `devops/terraform/environments/prod/variables.tf:11` (`variable image_tag`); plus `devops/terraform/environments/prod/terraform.tfvars.example:7`, `devops/terraform/environments/prod/main.tf:7`, `devops/terraform/modules/stack/variables.tf:24`.

**Evidence.** `variable "image_tag"` defaults to `"latest"`, `tfvars.example` ships `image_tag = "latest"`, and `main.tf` passes it straight through the stack to the ECS task defs. Prod thus runs a floating tag by default. This is the IaC counterpart to the deploy-script bug in OPS-01.

**Failure scenario.** A new push to `:latest` silently changes prod on the next task recycle; a bad build cannot be pinned or rolled back by tag, and ECS image caching makes the running version non-deterministic.

**Suggested fix.** Require an explicit immutable tag (git SHA) in prod; drop the `"latest"` default so `plan` fails without one, and enable ECR immutable tags (see OPS-09).

**Verification.** Confirmed 3/3 adversarial verifiers. `prod/variables.tf:11` `image_tag` default is `"latest"`, passed straight through stack→ecs; `tfvars.example` ships `latest`. deploy.sh overrides at runtime, but the IaC default is unpinned.

---

<a id="ops-08"></a>
### OPS-08 — ALB lacks access logs, WAF, deletion protection, and drop_invalid_header_fields
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/74)) · Confidence: high (3/3 verifiers) · Effort: M · WS38

**Update (2026-07-10).** Fixed: ALB sets `drop_invalid_header_fields = true`, ships access logs to a private S3 bucket (90-day lifecycle + ELB delivery policy), and associates a regional WAFv2 web ACL (AWS Managed Common + Known Bad Inputs). Stack knob `alb_deletion_protection` is enabled on prod so a fat-finger destroy cannot delete the public entrypoint.

**Locations:** `devops/terraform/modules/alb/main.tf:9` (`aws_lb.this`).

**Note:** Merged with OPS-34 and OPS-35, which are near-exact duplicates covering the same ALB (access logs, `drop_invalid_header_fields`, deletion protection). The distinct plaintext-HTTP-fallback issue on the same file is kept separate as OPS-36.

**Evidence.** `aws_lb.this` is internet-facing (`internal = false`) yet sets no `access_logs` block, no `enable_deletion_protection`, and no `drop_invalid_header_fields`. A grep for `waf`/`access_logs`/`drop_invalid` across `devops/terraform` returns nothing, and there is no `aws_wafv2_web_acl_association` anywhere — the only deletion-protection guard in the stack is on RDS.

**Failure scenario.** There is no L7 request audit trail for incident response on the public entrypoint; a fat-finger apply can delete the prod ALB; request-smuggling via malformed headers is not dropped; and no managed WAF rules protect the public API.

**Suggested fix.** Add `access_logs` to an S3 bucket, `enable_deletion_protection` on prod, `drop_invalid_header_fields = true`, and associate a WAFv2 web ACL.

**Verification.** Confirmed 3/3 adversarial verifiers. `aws_lb.this` is `internal=false` and grep across `devops/terraform` shows no waf/access_logs/drop_invalid and no deletion_protection on the ALB (only RDS has it); the hardening gaps on a public ALB are real.

---

<a id="ops-09"></a>
### OPS-09 — ECR repositories use MUTABLE image tags, allowing tag overwrite
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/75)) · Confidence: high (5/5 verifiers) · Effort: S · WS38

**Update (2026-07-10).** Fixed: ECR repositories set `image_tag_mutability = "IMMUTABLE"` so a re-push cannot overwrite a tag that ECS task definitions still reference by `${var.image_tag}`. Deploy continues to use unique git-SHA tags (`IMAGE_TAG` / prod `image_tag`); optional customer-managed KMS encryption remains out of scope (AES-256 at rest is the AWS default).

**Locations:** `devops/terraform/modules/ecr/main.tf:7` (`aws_ecr_repository.this`).

**Note:** Merged with OPS-37 (same file/line, "MUTABLE tags, no CMK encryption"); OPS-37 additionally flags the absent `encryption_configuration` KMS CMK, folded in below.

**Evidence.** `image_tag_mutability = "MUTABLE"`. Deploys reference images by `${var.image_tag}` (`ecs/main.tf` L7-9), not by digest, so a pushed tag can be silently replaced. There is also no `encryption_configuration` (KMS CMK) on the repository. Combined with mutable tags, this breaks reproducible/verifiable deploys and rollbacks.

**Failure scenario.** An attacker or an accidental re-push with the same tag overwrites the running image reference; the next task launch pulls tampered code with no diff in the task definition.

**Suggested fix.** Set `image_tag_mutability = "IMMUTABLE"`, deploy by immutable tag or image digest, and optionally add a KMS `encryption_configuration`.

**Verification.** Confirmed 5/5 adversarial verifiers. `image_tag_mutability="MUTABLE"` confirmed and deploys reference by tag (ecs main.tf) not digest, so tags can be silently overwritten; valid supply-chain hardening finding at medium.

---

<a id="ops-10"></a>
### OPS-10 — ElastiCache Redis broker has no in-transit/at-rest encryption and no AUTH token
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/76)) · Confidence: high (5/5 verifiers) · Effort: M · WS38

**Update (2026-07-10).** Fixed: Redis module always uses `aws_elasticache_replication_group` with `transit_encryption_enabled`, `at_rest_encryption_enabled` (optional CMK via `kms_key_id`), and `auth_token` from stack `random_password` stored as Secrets Manager `REDIS_PASSWORD`. ECS sets `REDIS_TLS=true` so Settings builds `rediss://` Celery broker/result URLs. Also closes merged OPS-11/OPS-12/OPS-13/OPS-50.

**Locations:** `devops/terraform/modules/redis/main.tf:9` (`aws_elasticache_cluster.this`); plus `devops/terraform/modules/redis/variables.tf:1`.

**Note:** Merged from five records reporting the same defect: OPS-11, OPS-12, OPS-13 (all `redis/main.tf:9`) and the low-rated OPS-50 (`redis/variables.tf` exposes no encryption/auth toggle). All describe the missing `transit_encryption_enabled`, `at_rest_encryption_enabled`, and `auth_token` on the Celery broker.

**Evidence.** `aws_elasticache_cluster.this` omits `transit_encryption_enabled`, `at_rest_encryption_enabled`, and `auth_token`, and `variables.tf` exposes no toggle for any of them. Redis is the Celery broker and result backend (module comment L1), so broker traffic and stored payloads — including task args carrying job/user identifiers, applicant PII, and credential context — are plaintext and unauthenticated. A single-node cache cluster cannot enable in-transit encryption, so this requires switching to a replication group.

**Failure scenario.** Any workload landing in the tasks SG (or an in-VPC pivot from a compromised task) can read/write the broker: inspect Celery task args, inject or alter tasks (including auto-apply jobs), or sniff plaintext broker traffic. At-rest snapshots are also unencrypted.

**Suggested fix.** Use an `aws_elasticache_replication_group` with `transit_encryption_enabled = true`, `at_rest_encryption_enabled = true`, an `auth_token` sourced from Secrets Manager, and a KMS key; wire the token into the Celery `rediss://` URL secret, and expose these as module variables.

**Verification.** Confirmed 5/5 adversarial verifiers (across the merged records). All three encryption/auth settings are absent; the redis SG restricts ingress to the tasks SG in private subnets, so exploitation needs an in-VPC/task-container foothold — matching medium (elevated preconditions) rather than high.

---

<a id="ops-14"></a>
### OPS-14 — Tasks security group ingress from ALB opens all TCP ports 0-65535
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/77)) · Confidence: high (5/5 verifiers) · Effort: S · WS38

**Update (2026-07-10).** Fixed: `tasks_from_alb` replaced with `tasks_http_from_alb` (port 80) and `tasks_api_from_alb` (port 8000), both sourced from the ALB SG — worker metrics `:9090` is no longer reachable via the ALB rule ([PR](https://github.com/davidcristian/HeadStart/pull/77)).

**Update (2026-07-10, FRO-08).** Frontend target port moved from 80 → **8080** (unprivileged nginx); `tasks_http_from_alb` and the ALB/ECS frontend wiring follow that port.

**Locations:** `devops/terraform/modules/security/main.tf:61` (`aws_security_group_rule.tasks_from_alb`).

**Note:** Merged from four records on the same rule: OPS-15 (medium) plus OPS-52 and OPS-53 (low). All flag the same `from_port=0/to_port=65535` ingress from the ALB SG.

**Evidence.** `tasks_from_alb` uses `from_port = 0` / `to_port = 65535` sourced from the ALB SG. The ALB only targets container ports 8000 (api) and 80 (frontend); worker/beat expose no ALB targets. All four services share `var.tasks_security_group_id`, and the worker exposes `containerPort 9090` (metrics), so the ALB SG can reach that port too. Opening the full range violates least-privilege.

**Failure scenario.** A compromised or misconfigured ALB-SG member can reach any port an ECS task listens on (e.g. the worker's 9090 metrics/debug endpoint), widening lateral-movement blast radius beyond the two intended service ports.

**Suggested fix.** Replace the wildcard range with two explicit ingress rules scoped to ports 80 and 8000 (per target-group port), sourced from the ALB SG.

**Verification.** Confirmed 5/5 adversarial verifiers. `tasks_from_alb` uses `from_port=0/to_port=65535` while the ALB only targets 8000/80; the worker (sharing the tasks SG) exposes 9090, so the range violates least-privilege. The source is the internal ALB SG (not the internet), which gates exploitability — medium is fair.

---

<a id="ops-16"></a>
### OPS-16 — ntfy_default_topic defaults to static public topic "headstart-change-me"
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/57)) · Confidence: high (3/3 verifiers) · Effort: S · WS31

**Update (2026-07-10).** Fixed: Terraform `ntfy_default_topic` is required (no default) with validation rejecting empty/`change-me` placeholders in the stack module and beta/prod env wrappers; tfvars examples no longer assign the public topic; non-local `Settings` boots refuse `headstart-change-me` and any topic containing `change-me` via `secret_policy.assert_ntfy_topic_safe_for_environment` (also closes [XCT-26](../cross-cutting.md#xct-26)).

**Locations:** `devops/terraform/modules/stack/variables.tf:82` (`ntfy_default_topic`); plus `devops/terraform/environments/prod/variables.tf:55`, `devops/terraform/environments/prod/terraform.tfvars.example:25`, `devops/terraform/environments/beta/terraform.tfvars.example:27`, `devops/terraform/modules/stack/main.tf:163`, `backend/app/core/config.py:167`.

**Note:** Merged with OPS-32 (the low-rated prod-tfvars-specific instance of the same public-topic default).

**Evidence.** `ntfy_default_topic { default = "headstart-change-me" }` is wired to the `NTFY_DEFAULT_TOPIC` env var; the prod variable and both `tfvars.example` files repeat the literal, and the stack defaults `ntfy_default_server_url` to `https://ntfy.sh`. ntfy.sh topics are unauthenticated: anyone who knows the topic name can read and publish to it. No validation rejects the placeholder for non-local environments.

**Failure scenario.** An operator applies with defaults (or copies `tfvars.example` verbatim), and job-alert notifications — titles, URLs, and search terms — publish to a globally guessable public ntfy.sh topic that anyone can subscribe to.

**Suggested fix.** Remove the default (force an explicit unique value) or generate a random suffix, and add validation that rejects the `change-me` placeholder for non-local envs; consider defaulting to a private ntfy server.

**Verification.** Confirmed 3/3 adversarial verifiers. The default `headstart-change-me` is wired to `NTFY_DEFAULT_TOPIC` and repeated in the prod var/tfvars with no validation; an unauthenticated ntfy.sh topic leaks alert content if the operator forgets to override.

---

<a id="ops-17"></a>
### OPS-17 — Deploy rolls all ECS services regardless of DB migration success (fire-and-forget)
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done · Confidence: high (5/5 verifiers) · Effort: M · WS36

**Locations:** `scripts/deploy.sh:26` (`deploy migrate step` / `run-task migrate`).

**Note:** Merged from OPS-18 (same file/line, same fire-and-forget migration defect).

**Evidence.** `aws ecs run-task --task-definition headstart-migrate ... || warn` (line 26) does not wait for or check the migrate task; `run-task` returns on submission, not completion, and failure is only a warning. The loop at line 33 then unconditionally `update-service --force-new-deployment`s api/frontend/worker/beat.

**Failure scenario.** A migration that fails or is still running lets new app images roll against an old or partial schema → runtime 500s until noticed, or the schema change races the new code. No gate stops the rollout, and a failed migration only emits a non-fatal warning.

**Suggested fix.** Capture the `run-task` ARN, `aws ecs wait tasks-stopped`, assert `exitCode == 0`/inspect `stopReason`, and abort the service roll on migration failure.

**Verification.** Confirmed 5/5 adversarial verifiers. At deploy.sh:26-40, `run-task` with `|| warn` returns on submission not completion, then the unconditional `update-service` loop rolls all services regardless of migration result. Impact is condition-gated on a slow/failing migration and yields recoverable 500s, not data loss, so medium.

---

<a id="ops-19"></a>
### OPS-19 — No dependency vuln scanning (pip-audit / npm audit / Dependabot) in repo
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: certain (3/3 verifiers) · Effort: S · WS37

**Locations:** `.github/workflows/ci.yml:1` (`ci`).

**Evidence.** A grep for `audit|safety|snyk|pip-audit|osv|trivy|dependabot|cve` across `.github(.disabled)/` and `scripts/` returns nothing, and there is no `.github/dependabot.yml` or `renovate.json`. The now-live ci.yml gate is lint + type + test + coverage only — SCA is entirely absent.

**Failure scenario.** A newly disclosed CVE in a pinned or floating dependency (e.g. the next `cryptography`/`celery` advisory) ships to production undetected because no build step flags vulnerable dependencies.

**Suggested fix.** Add `pip-audit` (backend) and `npm audit --audit-level=high` (frontend) as a CI job, plus a Dependabot/Renovate config for automated bump PRs.

**Verification.** Confirmed 3/3 adversarial verifiers. ci.yml is now live under `.github/workflows/` but has no SCA step, there is no `dependabot.yml`/`renovate.json`, and grep for audit/pip-audit/trivy/dependabot/cve returns nothing; low severity is fair.

**Update (2026-07-11).** Fixed: `just audit-backend` runs `pip-audit --disable-pip` on the three hashed lockfiles in CI; Dependabot watches `/backend` pip weekly (frontend npm audit + Dependabot already shipped with FRO-12). — [PR](https://github.com/davidcristian/HeadStart/pull/188).

---

<a id="ops-20"></a>
### OPS-20 — All GitHub Actions pinned to floating major-version tags, not commit SHAs
⚪ **LOW** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/194)) · Confidence: high (3/3 verifiers) · Effort: S · WS37

**Locations:** `.github/workflows/ci.yml:20` (`uses:`); plus ci.yml:21/45/46, `.github/workflows/deploy.yml:31/34/41`, `.github/workflows/terraform.yml:24/25`.

**Evidence.** Every `uses:` references a mutable tag (`checkout@v4`, `configure-aws-credentials@v4`, `amazon-ecr-login@v2`, `setup-python@v5`, `setup-node@v4`, `setup-terraform@v3`). Tags are mutable; a re-pointed or compromised tag would run attacker code with the job's OIDC/AWS credentials and secrets.

**Failure scenario.** An upstream tag re-point or compromise makes the deploy job (`id-token: write`, AWS role, ECR push) run malicious code that exfiltrates AWS credentials or pushes a poisoned image.

**Suggested fix.** Pin every third-party action to a full commit SHA (with a version comment) and add Dependabot to bump the SHAs.

**Resolution.** `ci.yml` / `deploy.yml` / `terraform.yml` now pin every `uses:` to a 40-char commit SHA (version comment retained); `.github/dependabot.yml` watches `github-actions` weekly. Regression: `backend/tests/devops/test_ops20_action_pins.py`.

**Verification.** Confirmed 3/3 adversarial verifiers. All `uses:` are floating tags (a real supply-chain gap). ci.yml is now live under `.github/workflows/`, so its floating action tags execute on push/PR; the deploy.yml/terraform.yml `uses:` are present in `.github/workflows/` but stay dormant behind the `workflow_dispatch`/`vars.AWS_ROLE_ARN` guards.

---

<a id="ops-21"></a>
### OPS-21 — CI Slack-failure notify guarded by env var never set at that scope, never fires
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: XS · WS37

**Locations:** `.github/workflows/ci.yml` (`notify job`).

**Evidence.** The step's `if: ${{ env.SLACK_WEBHOOK_URL != '' }}` was evaluated before the step-level `env:` applied, and no job- or workflow-level env set it. `env.SLACK_WEBHOOK_URL` was therefore always `''` at the `if`, so the Slack alert was silently skipped on every failure.

**Failure scenario.** CI fails on a push to main and no Slack alert is ever sent, because the guard sees an empty env var — giving false confidence that failures are surfaced.

**Suggested fix.** Reference the secret directly in the guard (`if: secrets.SLACK_WEBHOOK_URL != ''`) or set `SLACK_WEBHOOK_URL` at job level.

**Resolution.** `notify` maps `SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}` at **job** level (visible to step `if`); the step no longer relies on step-scoped env for the guard. Regression: `backend/tests/devops/test_ops21_ci_slack_notify.py`.

**Verification.** Confirmed 3/3 adversarial verifiers. Per GitHub docs, step-level env is not available in that same step's `if`, so `env.SLACK_WEBHOOK_URL` is always `''` when only set under the step.

---

<a id="ops-22"></a>
### OPS-22 — CI reimplements gate steps inline instead of make check, risking drift
⚪ **LOW** · 🔁 consistency · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: S · WS37

**Locations:** `.github/workflows/ci.yml` (`backend` / `frontend` jobs); `scripts/check.sh`; `justfile` `check` / `build-frontend`.

**Evidence.** AGENTS.md §4 mandates running "always via `scripts/`" / one `just check`, but CI previously listed separate lint/typecheck/test/`npm run build` steps. Those already called just recipes after OPS-04, but a future edit could reintroduce hand-rolled `ruff`/`pytest`/`npm` gates that diverge from `scripts/`.

**Failure scenario.** A future edit to `scripts/` or the justfile (e.g. adding a check or changing coverage flags) does not run in CI, so a change that fails `just check` locally can pass CI or vice-versa.

**Fix.** `scripts/check.sh` composes `lint.sh` + `typecheck.sh` + `test.sh` (scoped `--backend` / `--frontend` / `--scripts`). `just check` delegates to it. CI runs `just check --backend`, `just check --scripts`, `just check --frontend`, and `just build-frontend` (`scripts/build-frontend.sh`) — no hand-rolled tool steps. Regression tests lock the wiring.

**Verification.** Confirmed 3/3 adversarial verifiers. CI hand-rolls ruff/black/mypy/pytest and npm steps rather than calling `make check`; a real drift risk, correctly rated low consistency.

---

<a id="ops-23"></a>
### OPS-23 — Deploy assumes AWS OIDC role with no in-workflow ref scoping or branch-protection note
⚪ **LOW** · 🔒 security · Status: ✅ done · [PR](https://github.com/davidcristian/HeadStart/pull/202) · Confidence: medium (3/3 verifiers) · Effort: S · WS37

**Locations:** `.github/workflows/deploy.yml:33` (`Configure AWS credentials (OIDC)`).

**Evidence.** `configure-aws-credentials@v4` assumes `vars.AWS_ROLE_ARN` on every push to main/master and any `workflow_dispatch`; the dev deploy path has no approval. Security rests entirely on the external IAM trust-policy `sub` claim, and nothing documents that it must pin `repo:*:ref:refs/heads/main`.

**Failure scenario.** If the IAM trust policy is written with a wildcard `sub`, any workflow or branch in the repo can assume the deploy role; the workflow offers no guardrail or documented assumption.

**Suggested fix.** Add `role-session-name`/audience, document the required trust-policy `sub` scoping, and require an approving environment for the dev push path too.

**Verification.** Confirmed 3/3 adversarial verifiers. The workflow is now present in `.github/workflows/` but stays dormant (manual `workflow_dispatch` only, gated on `vars.AWS_ROLE_ARN`); once enabled it uses environment protection but has no in-workflow ref scoping and no documented trust-policy sub pinning — a legitimate hardening/doc nit, low.

**Resolution.** `deploy.yml` job `if` requires `refs/heads/main|master` in addition to `AWS_ROLE_ARN`; OIDC step sets `audience: sts.amazonaws.com` and `role-session-name: headstart-deploy-<run_id>`; workflow header + deployment docs document IAM `sub` pinning, Environment reviewers, and branch protection. Regression: `backend/tests/devops/test_ops23_deploy_oidc.py`.

---

<a id="ops-24"></a>
### OPS-24 — terraform plan on pull_request injects TF secrets + assumes AWS role on PR code
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: M · WS37

**Locations:** `.github/workflows/terraform.yml:42` (`Plan step`).

**Evidence.** On `pull_request` the Plan step (when `AWS_ROLE_ARN` is set) exposes `TF_VAR_db_password`/`jwt_secret`/`credentials_secret_key` (secrets, lines 44-46) and runs Terraform against a PR checkout under the assumed AWS role. A same-repo branch PR could exfiltrate these via plan-time provider or data-source code.

**Failure scenario.** A contributor or compromised write-access account opens a `devops/terraform/**` PR with an external data source that leaks the TF_VAR secrets / assumed AWS creds during `plan`.

**Suggested fix.** Gate the credentialed plan behind an approved environment/label, scope OIDC trust to protected refs, and never expose deploy secrets on untrusted PR checkouts.

**Verification.** Confirmed 3/3 adversarial verifiers. The workflow is now present in `.github/workflows/` but the credentialed Plan step stays dormant: it is gated on `vars.AWS_ROLE_ARN != ''`, so it runs nothing AWS-touching until that variable/secrets are configured; real only once enabled, so low.

**Resolution.** PR `validate` job runs `fmt`/`init -backend=false`/`validate` only (no `TF_VAR_*`, no OIDC). Credentialed `plan` is a separate `workflow_dispatch` job gated on `AWS_ROLE_ARN` + `refs/heads/main|master`, targets the `beta`/`prod` GitHub Environment, assumes AWS via OIDC (`audience` + `role-session-name: headstart-tf-plan-<run_id>`), and inits remote state with `vars.TF_STATE_BUCKET` (OPS-29). Docs + regression in `test_ops24_terraform_plan_trust.py`. — [PR](https://github.com/davidcristian/HeadStart/pull/203).

---

<a id="ops-27"></a>
### OPS-27 — Worker image installs playwright system deps as root but retains them at runtime
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (2/3 verifiers) · Effort: M · WS38

**Locations:** `backend/Dockerfile:29` (`worker stage`).

**Evidence.** The worker stage runs `playwright install --with-deps chromium` as root (necessary), then switches to `USER appuser` — which is correct. However, the resulting image ships a full Chromium plus its many apt libraries in the worker that scrapes untrusted sites, enlarging the attack surface versus a hardened browser sandbox. No seccomp / no-sandbox posture is stated.

**Failure scenario.** A Chromium/renderer vulnerability reached while scraping a malicious job site runs in the worker container; the large bundled dependency surface increases exploitability, mitigated only by `appuser`.

**Suggested fix.** Document/enforce Chromium sandbox flags and a seccomp profile for the worker; consider a minimal browser base image. Low-priority hardening.

**Verification.** Confirmed 2/3 adversarial verifiers (1 refuted). The worker stage does ship Chromium + apt deps (Dockerfile L33-34) for untrusted-site scraping; it is intentional design and runs as `appuser`, so this is speculative defense-in-depth, correctly rated low.

**Resolution.** Chromium launch drops `--no-sandbox` by default (`PLAYWRIGHT_NO_SANDBOX` local/test-only, rejected elsewhere); ECS worker applies RuntimeDefault seccomp + capability drop + init. See [PR #207](https://github.com/davidcristian/HeadStart/pull/207).

---

<a id="ops-28"></a>
### OPS-28 — Backend Dockerfile copies app source before pip install, breaking dep caching
⚪ **LOW** · ⚡ perf · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: S · WS38

**Locations:** `backend/Dockerfile:17` (`base`).

**Evidence.** The base stage does `COPY pyproject.toml`, then `COPY app ./app`, then `pip install .` (L19). The whole `app/` tree is in the install layer, so any source-only change invalidates it and reinstalls all dependencies — directly contradicting the L15 comment "Install dependencies first (better layer caching)."

**Failure scenario.** Every code change triggers a full dependency reinstall on rebuild, slowing CI/CD and local iteration; the stated caching benefit is never realized.

**Suggested fix.** Install dependencies from `pyproject.toml` before copying app source (or split the install) so source edits do not bust the deps layer.

**Verification.** Confirmed 3/3 adversarial verifiers. Dockerfile L17-19 copies app source before `pip install .`, so any source change busts the deps layer, contradicting the L15 comment; a real caching defect.

**Resolution.** Already fixed by XCT-14 ([PR #20](https://github.com/davidcristian/HeadStart/pull/20)): hashed `requirements.txt` installs before `COPY app`, then `pip install --no-deps .`. Tracker close adds an OPS-28 regression on layer order plus deployment.md / Dockerfile comments so the caching contract cannot regress silently. — [PR #208](https://github.com/davidcristian/HeadStart/pull/208).

---

<a id="ops-29"></a>
### OPS-29 — State backend bucket is unresolved CHANGEME placeholder committed for both envs
⚪ **LOW** · 🔁 consistency · Status: ✅ done · Confidence: medium (2/3 verifiers) · Effort: XS · WS36

**Locations:** `devops/terraform/environments/prod/backend.tf:6` (`backend s3`); plus `devops/terraform/environments/beta/backend.tf:6`.

**Evidence.** `bucket = "CHANGEME-headstart-tfstate"` is hardcoded in both env `backend.tf` files; a comment says to edit the placeholders or pass `-backend-config`. Dev and prod share one lock table (keyed by state key), which is acceptable.

**Failure scenario.** An operator who runs `terraform init` without `-backend-config` targets a non-existent CHANGEME bucket and init fails; editing in place risks committing a real bucket name or env drift.

**Suggested fix.** Keep the bucket out of the committed `backend.tf` (partial config) and document the required `-backend-config` file, or template it per env.

**Verification.** Confirmed 2/3 adversarial verifiers (1 refuted). Both `backend.tf` files hardcode `bucket = "CHANGEME-headstart-tfstate"`; init fails fast (safe failure) and `-backend-config` is documented, so a minor consistency/UX issue at low.

**Resolution.** Committed `backend.tf` files are partial S3 backends (no `bucket`); operators pass the bucket via `-backend-config` / gitignored `backend.hcl` from `backend.hcl.example`. Docs + bootstrap script updated; regression in `test_terraform_backend_partial.py`. — [PR](https://github.com/davidcristian/HeadStart/pull/183).

---

<a id="ops-30"></a>
### OPS-30 — dev and prod share identical VPC CIDR 10.20.0.0/16 (never overridden)
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: S · WS36

**Fixed in** [PR #184](https://github.com/davidcristian/HeadStart/pull/184): beta pins `10.20.0.0/16`, prod pins `10.30.0.0/16` with matching subnet CIDRs.

**Locations:** `devops/terraform/environments/prod/main.tf:1` (`module.stack (prod)`); plus `devops/terraform/environments/beta/main.tf:1`, `devops/terraform/modules/stack/variables.tf:8`, `devops/terraform/modules/stack/variables.tf:15`.

**Evidence.** Neither env passes `vpc_cidr`/`public_subnet_cidrs`/`private_subnet_cidrs`, so both inherit the stack defaults `10.20.0.0/16` and the same `/24`s (`stack/variables.tf:8-22`). Dev and prod networks are address clones.

**Failure scenario.** If dev and prod are ever VPC-peered (shared bastion, cross-env migration) or peered to a corp CIDR, the overlapping ranges make peering impossible and routing ambiguous.

**Suggested fix.** Give each environment a distinct `vpc_cidr` (e.g. dev `10.20/16`, prod `10.30/16`) via the env `main.tf` module call.

**Verification.** Confirmed 3/3 adversarial verifiers. Neither `dev/main.tf` nor `prod/main.tf` passes `vpc_cidr`/subnet CIDRs, so both inherit stack defaults `10.20.0.0/16` and identical `/24`s; a real dev-prod address clone.

---

<a id="ops-31"></a>
### OPS-31 — Prod provider lacks allowed_account_ids guard against wrong-account apply
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: XS · WS36

**Locations:** `devops/terraform/environments/prod/providers.tf:1` (`provider aws`); plus `devops/terraform/environments/beta/providers.tf:1`.

**Evidence.** `provider "aws" { region = var.region }` is the entire block — identical to dev. There is no `allowed_account_ids`, `assume_role`, or `profile` pin, so ambient AWS credentials alone decide the target account for a prod apply.

**Failure scenario.** An operator with dev credentials exported runs `terraform apply` in `prod/`; the prod stack provisions into the wrong account, or a fat-fingered credential targets an unintended account with no guardrail.

**Suggested fix.** Add `allowed_account_ids` (and ideally `assume_role`/`profile`) to the prod provider so apply fails fast against the wrong account.

**Verification.** Confirmed 3/3 adversarial verifiers. `prod/providers.tf` contains only `region = var.region` with no `allowed_account_ids`/`assume_role` guard, identical to dev; a genuine defense-in-depth gap.

---

<a id="ops-33"></a>
### OPS-33 — prod tfvars.example primes inline plaintext secrets in terraform.tfvars
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: XS · WS36

**Locations:** `devops/terraform/environments/prod/terraform.tfvars.example:9` (`db_password/jwt_secret/credentials_secret_key`); plus `devops/terraform/environments/beta/terraform.tfvars.example:12`.

**Evidence.** The prod `tfvars.example` lists the three core secrets as inline assignments (l9-11). Although comments say "prefer env vars," the example primes users to put real prod secrets into `terraform.tfvars` (gitignored only by convention), unlike `smtp_password`, which is shown as env-var-only.

**Failure scenario.** An operator copies `prod/tfvars.example`, fills real secrets inline, and the file is later force-added or backed up outside git, leaking the credentials-encryption key and JWT signing secret.

**Suggested fix.** Present these three prod secrets only as commented `TF_VAR_*` env-var exports, matching how `smtp_password` is shown.

**Verification.** Confirmed 3/3 adversarial verifiers. The prod `tfvars.example` lists `db_password`/`jwt_secret`/`credentials_secret_key` as inline (change-me) assignments while `smtp_password` is env-var-only; a real hardening nit for an example file, low.

---

<a id="ops-36"></a>
### OPS-36 — ALB serves API/frontend over plaintext HTTP when no ACM certificate is configured
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: M · WS38

**Locations:** `devops/terraform/modules/alb/main.tf:54` (`aws_lb_listener.http`).

**Evidence.** When `https_enabled` is false, the port-80 listener forwards to the frontend and the `api_http` rule forwards `/api/*` directly, with no redirect. A deploy without `domain_name`/cert — the default in both envs, which pass `acm_certificate_arn = ""` — exposes login/JWT/credentials traffic in cleartext.

**Failure scenario.** An operator deploys prod without setting `domain_name` + `route53_zone_id` (both default to `""`); the public ALB then serves auth and site-credential API traffic over unencrypted HTTP, exposing JWTs and passwords on the wire.

**Suggested fix.** Require a certificate for non-dev environments (validation on `environment == prod`) or refuse to create a plaintext-forwarding listener outside local/dev.

**Verification.** Confirmed 3/3 adversarial verifiers. Prod defaults `domain_name`/`route53_zone_id`/`acm_certificate_arn` all to `""`, so `https_enabled=false` and the port-80 listener forwards API/frontend in cleartext; no guard forces HTTPS. Needs operator misconfig, so low.

---

<a id="ops-38"></a>
### OPS-38 — ECS container definitions lack healthCheck, read-only root filesystem, and non-root user
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: M · WS38

**Locations:** `devops/terraform/modules/ecs/main.tf:40` (`backend_container / worker_container`).

**Note:** Merged with OPS-39 (same task defs, `ecs/main.tf:41`), which additionally emphasizes non-root user and `linuxParameters`.

**Evidence.** The container definitions (`backend_container`, `worker_container`, frontend) `jsonencode` only name/image/command/env/secrets/log. They set no `healthCheck`, no `readonlyRootFilesystem`, no `user` (so they run as the image default, often root), and no `linuxParameters`. worker/beat also have no ALB health check, so only ECS process liveness is tracked.

**Failure scenario.** A wedged-but-alive worker/beat container is never recycled (no container `healthCheck`), and an RCE in the API/worker container — which processes untrusted scraped HTML and recruiter email — runs as root on a writable rootfs, easing persistence and privilege escalation within the container.

**Suggested fix.** Add a `healthCheck` to each container def, set `readonlyRootFilesystem = true` (with tmpfs/volumes for scratch), and run as a non-root `user`.

**Verification.** Confirmed 3/3 adversarial verifiers. All four task defs omit `readonlyRootFilesystem`, `user`, `linuxParameters`, and container `healthCheck`; verified in `ecs/main.tf`; defense-in-depth, low.

---

<a id="ops-40"></a>
### OPS-40 — Reusable modules declare no required_providers version constraints
⚪ **LOW** · 🔁 consistency · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/211)) · Confidence: medium (3/3 verifiers) · Effort: S · WS38

**Locations:** `devops/terraform/modules/network/main.tf:1`; plus `devops/terraform/modules/rds/main.tf:1`, `devops/terraform/modules/redis/main.tf:1`, `devops/terraform/modules/ecs/main.tf:1`, `devops/terraform/modules/security/main.tf:1`.

**Note:** Merged with OPS-45 (same defect, "no required_providers pinning" across rds/redis/ecs/security modules).

**Update (2026-07-11).** Every reusable module under `devops/terraform/modules/*`
now ships `versions.tf` with `required_version >= 1.5.0` and
`hashicorp/aws >= 5.60` (`stack` also pins `hashicorp/random >= 3.6`).

**Evidence.** No `modules/**/versions.tf` or `required_providers`/`required_version` block exists in any module; a grep finds `terraform{}` pins only under `environments/`. Reusable modules should declare `required_providers` so a caller cannot bind an incompatible aws provider.

**Failure scenario.** A consumer wiring these modules from a root without a pinned aws provider (or with a drifted pin) gets undefined behavior — e.g. missing args like `transit_encryption` or changed resource defaults — with no fail-fast version guard.

**Suggested fix.** Add a `versions.tf` with `required_providers` (aws >= a pinned minimum) to each module, or one shared `versions.tf`.

**Verification.** Confirmed 3/3 adversarial verifiers. Grep confirms zero `required_providers`/`required_version` in `modules/` and no per-module `versions.tf`; only env dirs pin providers, so reused modules have no version floor — a genuine low consistency gap.

---

<a id="ops-41"></a>
### OPS-41 — VPC has no flow logs enabled
⚪ **LOW** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/212)) · Confidence: high (3/3 verifiers) · Effort: S · WS38

**Update (2026-07-11).** Network module publishes VPC flow logs (`traffic_type=ALL`) to CloudWatch `/vpc/{name}/flow-logs` with retention from stack `log_retention_days`; dedicated IAM role for `vpc-flow-logs.amazonaws.com`.

**Locations:** `devops/terraform/modules/network/main.tf:8` (`aws_vpc.this`).

**Note:** Merged with OPS-42 (exact duplicate, same file/line/claim).

**Evidence.** The network module creates the VPC/subnets/NAT but no `aws_flow_log` resource (a grep for `flow_log` across `devops/terraform` returns nothing). Traffic to task/RDS/Redis ENIs is unlogged at the network level.

**Failure scenario.** During incident response there is no record of accepted/rejected traffic to task/RDS/Redis ENIs, hampering detection of exfiltration or SG-bypass attempts and any reconstruction of which host talked to what.

**Suggested fix.** Add an `aws_flow_log` on the VPC delivering to CloudWatch Logs or S3 with appropriate retention.

**Verification.** Confirmed 3/3 adversarial verifiers. The network module creates VPC/subnets/NAT but grep finds no `aws_flow_log` anywhere; a genuine observability/forensics gap, low.

---

<a id="ops-43"></a>
### OPS-43 — RDS uses AWS-managed KMS key with no IAM auth, Performance Insights, log exports, or CMK rotation
⚪ **LOW** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/213)) · Confidence: medium (3/3 verifiers) · Effort: M · WS38

**Update (2026-07-11).** RDS module provisions a rotating CMK (`alias/{name}-rds`) for storage + Performance Insights, enables IAM DB auth, PI (7-day default), Enhanced Monitoring (60s), CloudWatch `postgresql`/`upgrade` log exports, and defaults `apply_immediately` to false. Secrets Manager CMK/rotation remains OPS-51.

**Locations:** `devops/terraform/modules/rds/main.tf:9` (`aws_db_instance.this`); plus `devops/terraform/modules/secrets/main.tf:9`.

**Note:** Merged from four heavily overlapping RDS-hardening records: OPS-44 (no CMK/PI/log exports/IAM auth, `apply_immediately`), OPS-46 (no PI/log exports/enhanced monitoring), and OPS-47 (default KMS on RDS + Secrets Manager, no secret rotation). All describe the same under-hardened primary datastore.

**Evidence.** `storage_encrypted = true` but no `kms_key_id` (uses the shared AWS-managed `aws/rds` key), no `iam_database_authentication_enabled`, no `performance_insights_enabled`, no `enabled_cloudwatch_logs_exports = ["postgresql"]`, and no enhanced `monitoring_interval`/`monitoring_role_arn`; `apply_immediately = true` applies changes disruptively. The secrets module (`secrets/main.tf`) likewise sets no `kms_key_id` and no `aws_secretsmanager_secret_rotation`, so DB password / JWT / Fernet keys never rotate.

**Failure scenario.** Auth relies solely on a static DB password; a leaked `TF_VAR_db_password` grants full DB access with no IAM-scoped alternative. Postgres logs (auth failures, slow queries) are never exported for audit; encryption uses a non-isolated shared key with no per-tenant key policy or rotation; and `apply_immediately` can cause an unexpected outage.

**Suggested fix.** Provision a customer-managed KMS key with a scoped key policy, enable `iam_database_authentication_enabled`, `performance_insights_enabled`, `enabled_cloudwatch_logs_exports`, and enhanced monitoring; add scheduled secret rotation; and gate `apply_immediately`.

**Verification.** Confirmed 3/3 adversarial verifiers (across merged records). `aws_db_instance.this` has no `kms_key_id`/IAM auth/PI/log exports/enhanced monitoring and `apply_immediately=true`; `secrets/main.tf` has no rotation resource; all defense-in-depth gaps, low.

---

<a id="ops-48"></a>
### OPS-48 — RDS module: no validation; deletion_protection/final-snapshot default unsafe
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: low (3/3 verifiers) · Effort: S · WS38

**Locations:** `devops/terraform/modules/rds/variables.tf:41` (`deletion_protection`); plus `devops/terraform/modules/rds/variables.tf:37`, `devops/terraform/modules/rds/main.tf:31`.

**Evidence.** `deletion_protection { default = false }` combined with `main.tf`'s `skip_final_snapshot = !deletion_protection` means an env that forgets the override gets no deletion protection AND no final snapshot on destroy. No validation enforces prod safety.

**Failure scenario.** A future or copy-paste environment reuses the module without setting `deletion_protection`; a `terraform destroy` then drops the DB with no final snapshot, causing irrecoverable data loss.

**Suggested fix.** Document the prod-required overrides and/or gate the final-snapshot setting independently of `deletion_protection` so destroys still snapshot.

**Verification.** Confirmed 3/3 adversarial verifiers. `deletion_protection` defaults to false and `main.tf` sets `skip_final_snapshot = !deletion_protection` with no validation, so a forgotten override yields a destroy with no final snapshot; a defense-in-depth gap, low.

---

<a id="ops-49"></a>
### OPS-49 — Redis cluster is single-node with no failover (Celery broker SPOF)
⚪ **LOW** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/67)) · Confidence: medium (3/3 verifiers) · Effort: M · WS38

**Update (2026-07-10).** Closed by OPS-05: redis module can provision a Multi-AZ replication group with automatic failover; prod enables it.

**Locations:** `devops/terraform/modules/redis/main.tf:9` (`aws_elasticache_cluster.this`).

**Evidence.** `num_cache_nodes = 1` is hardcoded on `aws_elasticache_cluster`; there is no replication group or `automatic_failover` even for prod. RDS exposes `multi_az`, but Redis has no HA knob, despite being the broker and result backend for all scheduling. (Related reliability facet also captured in the prod-hardening rollup OPS-05.)

**Failure scenario.** A single AZ or node failure takes down the Celery broker: no scraping, notifications, digests, or auto-apply until it is replaced, with in-flight task state lost.

**Suggested fix.** For prod, use `aws_elasticache_replication_group` with `automatic_failover_enabled` and more than one node; keep single-node only for dev via a variable.

**Verification.** Confirmed 3/3 adversarial verifiers. `aws_elasticache_cluster` hardcodes `num_cache_nodes=1` with no replication group/`automatic_failover` knob even for prod; the broker SPOF is real, low for an availability hardening gap.

---

<a id="ops-51"></a>
### OPS-51 — Secrets Manager secrets use default KMS key and no recovery window set
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: S · WS38

**Locations:** `devops/terraform/modules/secrets/main.tf:9` (`aws_secretsmanager_secret.this`).

**Evidence.** `aws_secretsmanager_secret` sets only name/tags: no `kms_key_id` (so `JWT_SECRET`, `CREDENTIALS_SECRET_KEY`, and `POSTGRES_PASSWORD` are encrypted under the shared `aws/secretsmanager` key) and no `recovery_window_in_days`, so deletes fall back to the 30-day default with no explicit policy.

**Failure scenario.** App-signing/crypto secrets share the account-default KMS key with no per-app key policy isolation; any principal with broad `kms:Decrypt` on the default key can read them without a secret-specific grant.

**Suggested fix.** Provision a customer-managed KMS key with a tight key policy for these secrets and set an explicit `recovery_window_in_days`.

**Verification.** Confirmed 3/3 adversarial verifiers. `aws_secretsmanager_secret` sets only name/tags, no `kms_key_id` or `recovery_window` across all modules; a genuine defense-in-depth gap, low.

---

<a id="ops-54"></a>
### OPS-54 — METRICS_TOKEN never set by Terraform; /metrics unauthenticated on prod tasks
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: S · WS21

**Locations:** `devops/terraform/modules/stack/main.tf` (`random_password.metrics_token` + `ecs_secrets`); plus `backend/app/main.py`, `backend/app/core/config.py`.

**Update (2026-07-10).** Fixed: stack generates `METRICS_TOKEN` with `random_password`, stores it in Secrets Manager, and always injects it into ECS task secrets so API and worker `/metrics` require Bearer auth on AWS.

**Evidence.** `config.py:113` defaults `metrics_token` to `''`, and `main.py:49` only enforces a bearer token when it is non-empty. The `ecs_environment` block (`stack/main.tf:150-169`) sets no `METRICS_TOKEN` and there is no corresponding tf variable, so prod always runs `/metrics` unauthenticated.

**Failure scenario.** A compromised task or a misconfigured SG lets an in-VPC caller scrape `/metrics` on api:8000 or worker:9090, exposing operational metrics with no auth. (Related to the over-broad tasks SG in OPS-14.)

**Suggested fix.** Add an optional `metrics_token` tf variable stored in Secrets Manager and injected as `METRICS_TOKEN`, or bind `/metrics` to a non-ingress port.

**Verification.** Confirmed 3/3 adversarial verifiers. `config.py:113` defaults `metrics_token` to `''` and `main.py:49-53` only enforces bearer when non-empty; no `METRICS_TOKEN` in `ecs_environment` and no tf var, so prod `/metrics` is unauthenticated. The failure scenario slightly overstates SG exposure (tasks 0-65535 is ALB-sourced, not full-VPC), but the core defect holds.

---

<a id="ops-55"></a>
### OPS-55 — LOG_LEVEL hardcoded to INFO in Terraform with no variable override
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: certain (3/3 verifiers) · Effort: XS · WS38

**Locations:** `devops/terraform/modules/stack/main.tf:153` (`ecs_environment`).

**Evidence.** `ecs_environment` sets `LOG_LEVEL = 'INFO'` as a literal. `config.py:26` exposes `log_level` as tunable and `.env.example:6` documents it, but there is no tf variable, so prod's log level cannot change without editing module source.

**Failure scenario.** During a prod incident an operator cannot raise verbosity to DEBUG via tfvars/env; they must patch the module and re-apply, delaying diagnosis.

**Suggested fix.** Expose a `log_level` tf variable (default `'INFO'`) and reference it in `ecs_environment`.

**Verification.** Confirmed 3/3 adversarial verifiers. `stack/main.tf:153` hardcodes `LOG_LEVEL='INFO'` with no tf variable (grep confirms none); `config.py:26` exposes it as tunable but prod cannot override without editing the module.

---

<a id="ops-56"></a>
### OPS-56 — Compose pins local images and ntfy to mutable :latest tags
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: XS · WS38

**Locations:** `docker-compose.yml:111` (`ntfy service`); plus `docker-compose.yml:43` (api.image), `docker-compose.yml:59` (backend-worker), `docker-compose.yml:102` (frontend).

**Note:** Merged with OPS-61 (broader "local images + ntfy on :latest" consistency record); same underlying pinning defect.

**Evidence.** `image: binwiederhier/ntfy:latest` is an unpinned external image, and the local images `headstart/backend:latest`, `backend-worker:latest`, and `frontend:latest` also float. Base images elsewhere are pinned (`postgres:16-alpine`, `redis:7-alpine`, `nginx:1.27-alpine`, `python:3.12-slim`, `node:22-alpine`), so `:latest` is inconsistent and ntfy silently pulls a new, unaudited image on every fresh pull.

**Failure scenario.** A `docker compose pull`/rebuild silently upgrades ntfy to a new (or compromised) upstream image with access to the notification path, and repeated runs can mismatch which local build a `:latest` tag points at, making the stack non-reproducible.

**Suggested fix.** Pin ntfy to a specific minor tag (ideally a digest), and tag local images with a build/version identifier rather than `:latest`.

**Verification.** Confirmed 3/3 adversarial verifiers. `binwiederhier/ntfy:latest` is the only floating third-party tag while postgres/redis are pinned, and local images use `:latest`; ntfy sits behind the optional offline profile, so low.

---

<a id="ops-57"></a>
### OPS-57 — api/worker/beat services define no healthcheck; frontend waits on api start not health
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: S · WS38

**Locations:** `docker-compose.yml:38` (`api/worker/beat/frontend`).

**Note:** Merged with OPS-60 (same defect: api/beat lack healthchecks, frontend `depends_on` has no `service_healthy`).

**Evidence.** `db` and `redis` have healthchecks, but `api`, `worker`, and `beat` have none, and `frontend.depends_on: [api]` (line 106) uses the short form with no `condition: service_healthy`. Compose starts the frontend as soon as the api container is created, not when uvicorn is serving — even though the image already exposes `/api/v1/health`.

**Failure scenario.** On `make up`, the frontend (and any orchestrator readiness gate) sees api as "up" before it accepts connections, so early requests during boot fail; there is no self-heal signal for a wedged worker/beat, and compose diverges from the ECS/ALB `/api/v1/health` check.

**Suggested fix.** Add an HTTP healthcheck to api (`GET /api/v1/health`), gate `frontend` on `condition: service_healthy`, and add liveness probes for worker/beat.

**Verification.** Confirmed 3/3 adversarial verifiers. api/worker/beat have no healthcheck and `frontend` uses short-form `depends_on: - api` with no `service_healthy` condition despite the image exposing `/api/v1/health`; a real readiness gap for a dev compose, low.

---

<a id="ops-58"></a>
### OPS-58 — Postgres (and Redis) published to host with weak default creds in compose
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: S · WS38

**Locations:** `docker-compose.yml:19` (`db service`); plus `docker-compose.yml:30` (redis).

**Note:** Merged with OPS-59 (same defect, extends to unauthenticated Redis on 6379).

**Evidence.** `ports: 5432:5432` publishes Postgres on the host and `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-headstart}` defaults the password (and user/db) to the literal `headstart` when `.env` is absent (matching `.env.example:59`). Redis maps `6379:6379` with no auth. Publishing binds `0.0.0.0`, so both are reachable from the LAN if the host firewall is open.

**Failure scenario.** A developer running `make up` on a shared/office network exposes Postgres (headstart/headstart) and unauthenticated Redis on all interfaces, allowing data theft or cache poisoning from the LAN.

**Suggested fix.** Bind published ports to `127.0.0.1` (e.g. `127.0.0.1:5432:5432`) or gate them behind a dev profile, and require an explicit `POSTGRES_PASSWORD` rather than a defaulted one.

**Verification.** Confirmed 3/3 adversarial verifiers. `5432:5432` and `6379:6379` are published on `0.0.0.0` with `POSTGRES_PASSWORD` defaulting to `headstart` and Redis unauthenticated; this is the dev-only compose (prod is ECS), so low is fair.

---

<a id="ops-62"></a>
### OPS-62 — aws-deploy-env.sh emits terraform/aws outputs into eval'd exports without safe quoting
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: low (3/3 verifiers) · Effort: S · WS37

**Locations:** `scripts/aws-deploy-env.sh:23` (`heredoc exports`); plus `scripts/aws-first-deploy.sh:194`.

**Evidence.** `ECS_CLUSTER`/`APP_URL`/`ACCOUNT` from `terraform output -raw` / `aws sts` are interpolated into `export X='${VAL}'` and then consumed via `eval "$(...)"` (aws-first-deploy.sh:194, Makefile). A value containing a single quote breaks the quoting under `eval`.

**Failure scenario.** If a terraform output (e.g. `app_url`/domain) ever contains a `'`, the eval'd string breaks, mis-setting env or running an unintended fragment. Low, because the outputs are IaC/operator-controlled.

**Suggested fix.** Avoid `eval`: write exports to a file and `source` it, or `printf %q` the values before emitting.

**Fix.** `aws-deploy-env.sh` emits each export with `printf %q` (no single-quoted heredoc). `eval "$(just aws-deploy-env)"` / `aws-first-deploy` keep working; a terraform/aws value containing `'` round-trips. Docs note the quoting. — [PR](https://github.com/davidcristian/HeadStart/pull/204)

**Verification.** Confirmed 3/3 adversarial verifiers. `export X='${VAL}'` heredoc is eval'd at aws-first-deploy.sh:194; a single quote breaks quoting, but values are IaC/operator-controlled (numeric account, fixed region, derived names), so exploitability is minimal.

---

<a id="ops-63"></a>
### OPS-63 — check_loc.sh strips REPO_ROOT via unquoted glob pattern in ${file#...}
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: XS · WS37

**Locations:** `scripts/check_loc.sh:20` (`printf offender path`).

**Evidence.** `printf "%s\t%s\n" "${lines}" "${file#${REPO_ROOT}/}"` uses `${REPO_ROOT}` as an unquoted glob pattern inside `${var#pattern}`; a checkout path with glob-special characters (`*?[]`) strips incorrectly.

**Failure scenario.** On a checkout whose absolute path contains `[` or `?`, offender paths in the failure report display wrong or absolute, confusing the fix. Cosmetic, not a gate bypass.

**Suggested fix.** Strip the prefix with a non-pattern method (literal substitution or `realpath --relative-to`), or escape the pattern.

**Fix.** Offender paths use a literal prefix check (`[[ "${file}" == "${prefix}"* ]]`) then `${file:${#prefix}}` so glob metacharacters in `REPO_ROOT` cannot mis-strip. Regression covers the anti-pattern and the `[dev]` path case. — [PR](https://github.com/davidcristian/HeadStart/pull/205)

**Verification.** Confirmed 3/3 adversarial verifiers. Line 20 uses `${file#${REPO_ROOT}/}` with `REPO_ROOT` unquoted as a glob pattern; it genuinely mis-strips on paths with `*?[]`, but impact is only cosmetic (path display), so low.

---

<a id="ops-64"></a>
### OPS-64 — ECS roll does not pin the just-pushed image digest (build→deploy provenance gap)
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: low (3/3 verifiers) · Effort: M · WS36

**Locations:** `scripts/deploy.sh:33` (`update-service loop`).

**Evidence.** `deploy.sh` pushes `IMAGE_TAG=${github.sha}` then force-new-deployments the services (line 33). Image resolution happens in the ECS task def; nothing pins or verifies the digest just built, so a task def on a floating tag could roll a different image than was tested, with no image attestation. This is the provenance-hardening facet of the release-integrity bug in OPS-01.

**Failure scenario.** If task defs reference a floating tag, `force-new-deployment` may pull an image other than the one this pipeline built/tested, breaking build→deploy provenance.

**Suggested fix.** Register a new task-def revision pinned to the pushed image digest and roll that revision; add image attestation/provenance.

**Fix.** After `build-images.sh --push`, `deploy.sh` calls `aws ecr describe-images` for `headstart-backend`, `headstart-backend-worker`, and `headstart-frontend`, caches the `sha256:…` digests, and passes `--image-digest` into `ecs_task_def retarget` so every registered revision uses `:{IMAGE_TAG}@{sha256:…}`. Missing/non-sha256 digests abort the deploy. Docs and regressions cover the resolve-before-retarget ordering. — [PR](https://github.com/davidcristian/HeadStart/pull/187)

**Verification.** Confirmed 3/3 adversarial verifiers. deploy.sh:33-40 does `force-new-deployment` without registering a task-def revision pinned to the pushed digest; if task defs use a floating tag, provenance is not guaranteed. A legit low-severity CI/CD hardening gap.

---

<a id="ops-65"></a>
### OPS-65 — Shell validation is bash -n syntax-only (no shellcheck)
⚪ **LOW** · 🧪 test · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: S · WS37

**Locations:** `scripts/validate-shell-scripts.sh:6` (`validate loop`).

**Note:** Merged with OPS-66 (same file/line, same "no shellcheck" defect).

**Evidence.** The loop runs only `bash -n` per script (parse-only) plus one `aws-first-deploy.sh --help` smoke test. `bash -n` cannot see unquoted expansions, unset-variable use, or `set -e` masking; a grep confirms `shellcheck` is never invoked anywhere, even though scripts carry `# shellcheck` directives and use `eval "$(...)"`.

**Failure scenario.** A quoting/word-splitting (SC2086-class) or unbound-variable bug in a deploy/setup script passes `make test --scripts` and ships; it only fails at runtime against AWS/prod (e.g. an env/terraform-output value with whitespace or metachars flowing into `eval`).

**Suggested fix.** Add `shellcheck` to the loop (and a pre-commit hook) with an agreed severity threshold, so SC2086-class bugs are caught in `make check` rather than production.

**Verification.** Confirmed 3/3 adversarial verifiers. `validate-shell-scripts.sh` runs only `bash -n` plus one `--help`; grep confirms `shellcheck` is never invoked despite scripts carrying `# shellcheck` directives — a real defense-in-depth gap, low.

**Fix.** `validate-shell-scripts.sh` now requires `shellcheck` and runs `shellcheck -x -S warning` on every `scripts/*.sh` after `bash -n` (pre-commit already calls this script). CI installs `shellcheck` before `just check --scripts`. Cleared the warnings it surfaced (SC2155 declare-then-export in `aws-first-deploy.sh`, unused `TF_DIR`, `cd || exit` in `lock-backend.sh`). `just setup` warns when shellcheck is missing; runbook + deployment.md document the host tool and gate.

---

<a id="ops-67"></a>
### OPS-67 — loc-cap exempts `*/tests/*` but frontend test-infra (`src/test/`) stays capped, disagreeing with the coverage-gate exclusion
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: high (delta audit) · Effort: S · WS42

**Locations:** `scripts/check_loc.sh:20`.

**Evidence.** Commit `702808e` added loc-cap exemptions `*/tests/*` (plural) and `*.test.ts | *.test.tsx`, and in the same commit excluded `frontend/src/test/**` from the coverage gate as "test infrastructure". But the frontend test-infra dir is `src/test/` (singular) and its files (`mockApiSamples.ts`, `mockApi.ts`, `renderWithClient.tsx`) don't end in `.test.ts(x)`, so the loc-cap still treats them as capped source — the LOC cap and the coverage exclusion now disagree about what counts as test infrastructure.

**Failure scenario.** `mockApiSamples.ts` is 268 lines; adding ~40 more mock samples pushes it past 300 and `make lint` fails, forcing an artificial split of a pure fixture file — the coverage-theater/arbitrary-split behavior the commit set out to eliminate.

**Suggested fix.** Add `*/src/test/*` to the loc-cap exemption `case` so the two mechanisms agree.

**Verification.** Confirmed (delta audit, 2026-07-03). `case ./frontend/src/test/utils.ts in */tests/*` does not match; no failure today (largest is 268 lines) but the mechanisms are inconsistent.

---

<a id="ops-68"></a>
### OPS-68 — loc-cap exemption keys on the `tests/` path segment, not on being a test
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: medium (delta audit) · Effort: S · WS42

**Locations:** `scripts/check_loc.sh:20`.

**Evidence.** `*/tests/*` exempts by directory name alone. No production file is affected today (the only `tests/` dir is `backend/tests`; the production tree has zero files >300 lines). Correctness relies on the invariant that a directory named exactly `tests/` only holds tests.

**Failure scenario.** A future change nesting a large generated/production module under any path with a `tests/` segment (e.g. `backend/app/foo/tests/generated_client.py`) is silently exempted from the 300-line cap, since the exemption is purely path-based.

**Suggested fix.** Tighten to the known test roots (`backend/tests/`, `frontend/src/**/*.test.*`, `frontend/src/test/`) rather than any `*/tests/*`.

**Verification.** Confirmed (delta audit, 2026-07-03). Convention-reliance / defense-in-depth note, no active defect.

---

<a id="ops-69"></a>
### OPS-69 — pre-commit formatter pins drifted from CI, causing reformat loops
⚪ **LOW** · 🔁 consistency · Status: ✅ done (WS37) · Confidence: high (observed 2026-07-09, shipping WS26) · Effort: S · WS37

**Locations:** `.pre-commit-config.yaml:18` (`ruff-pre-commit rev: v0.5.7`) and `:27` (`psf/black rev: 24.8.0`).

**Evidence.** The pinned hook versions had fallen far below what `pip install -e backend[dev]` resolves for the venv/CI (`ruff 0.15.20`, `black 26.5.1`, from the `ruff>=0.5.7` / `black>=24.8` floors). The config also ran a `ruff-format` hook that the CI gate (`scripts/lint.sh`: `ruff check app tests` + `black --check app tests`) does not — and at these versions ruff-format disagrees with black on 7 `app/` files (e.g. nested `a if b else c if d else e` ternaries: ruff-format 0.5.7 splits, black 24.8.0 collapses). The two formatters never converge, so `pre-commit run` reformat-loops on files CI considers clean, blocking the commit.

**Failure scenario.** Any commit touching a file where ruff-format and black disagree fails pre-commit forever (each hook reverts the other), forcing a `--no-verify` bypass or an unrelated rewrite to break the tie (hit on `backend/app/resumes/fields.py` while shipping WS26).

**Fix.** Bumped the pins to the CI/venv versions (ruff `v0.15.20`, black `26.5.1`), dropped the `ruff-format` hook (black is the sole formatter CI enforces), and scoped `ruff`/`black` to `^backend/(app|tests)/` so pre-commit mirrors the CI gate (which does not lint `alembic/`). Residual: the pyproject dev deps still float (`>=`), so the pins can re-drift on a future release — re-pin both together, or pin exact versions / add a lockfile (see [XCT-14](cross-cutting.md#xct-14)).

**Verification.** `pre-commit validate-config` OK; the `ruff`/`black` hooks pass on `app` files with no reformatting and skip `alembic/`; `ruff check app tests` + `black --check app tests` are green under the venv versions.
