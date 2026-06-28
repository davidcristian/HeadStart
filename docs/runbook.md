# Runbook

Operational tasks for running and debugging HeadStart. Everything has a script;
prefer `just` recipes over raw commands.

## Prerequisites & toolchain

`just setup` installs only the **project** toolchain (backend virtualenv +
deps, frontend `node_modules`, git pre-commit hooks). The following **host**
tools are assumed to already be present. `just setup` checks for them and warns,
but does not install them. On **Ubuntu 24.04 / WSL**:

| Tool | Needed for | Install (Ubuntu 24.04) |
| ---- | ---------- | ---------------------- |
| `just` | every command | `sudo apt install -y just` (or [other options](https://just.systems/man/en/packages.html)) |
| Docker engine + `docker compose` plugin | `just up`, `just build` | Docker Desktop with WSL integration, **or** native engine: `sudo apt install -y docker.io docker-compose-v2` |
| Python 3.12 + `venv` | backend, `just setup` | `sudo apt install -y python3 python3-venv` (3.12 ships with 24.04) |
| Node.js 20+ + `npm` | frontend | nodesource or `nvm` (Ubuntu's apt `nodejs` is too old) |
| `shellcheck` | `just check --scripts` / pre-commit shell gate | `sudo apt install -y shellcheck` |
| `git`, `openssl` | hooks, secret generation | usually preinstalled |
| **Terraform** | `just deploy` only (AWS) | [HashiCorp apt repo](https://developer.hashicorp.com/terraform/install) |
| **AWS CLI v2** | `just deploy` only (AWS) | [AWS docs](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |

`just setup` installs backend deps from the hashed lockfiles in
`backend/requirements*.txt` (see [ADR-0012](adr/0012-backend-dependency-lockfiles.md)).
After changing floors in `backend/pyproject.toml`, run `just lock-backend` and
commit the regenerated lockfiles before opening a PR.

Terraform and the AWS CLI are **not required for local development**. They are
needed only for deploying to AWS. See
[`devops/terraform/README.md`](../devops/terraform/README.md).

## Windows / WSL

Develop **inside WSL** (the repo lives on the Linux filesystem, e.g.
`/home/<you>/...`). Everything here is Bash + `just`, so it runs natively in WSL.
There is no PowerShell script set and none is needed. Do **not** run `just`
from Windows PowerShell/CMD; open the WSL (Ubuntu) shell instead.

- Docker: either install Docker Desktop on Windows and enable **WSL
  integration** for your distro, or install the native Docker engine inside WSL.
- Performance: keep the repo on the WSL ext4 filesystem, not under `/mnt/c`.

### Docker credential-helper error in WSL

If `just up`/`just build` fails while pulling a base image with an error like
`error getting credentials ... exec: "docker-credential-desktop.exe": ... not
found` (or any `.exe` credential helper), Docker is trying to call a Windows
credential helper that isn't on the WSL `PATH`. Work around it by pointing Docker
at a throwaway config with no `credsStore` so public images pull anonymously:

```bash
mkdir -p /tmp/dockercfg && echo '{}' > /tmp/dockercfg/config.json
DOCKER_CONFIG=/tmp/dockercfg just up      # or: docker compose ... / docker build ...
```

This is a host/WSL credential-helper quirk, not a project bug; the permanent fix
is to remove the broken `credsStore` line from `~/.docker/config.json` or repair
Docker Desktop's WSL integration.

## Local stack

```bash
cp .env.example .env      # first time only; set NTFY_DEFAULT_TOPIC
just up                   # build + start all services
just migrate              # apply DB migrations
just seed                 # optional: example sources
just logs                 # tail all logs
just down                 # stop everything
```

Endpoints:

- UI: <http://localhost:8080>
- API + docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/v1/health>
- Metrics (API): <http://localhost:8000/metrics>
- Metrics (worker): <http://localhost:9090/metrics> (when `METRICS_ENABLED=true`; send `Authorization: Bearer $METRICS_TOKEN` when the token is set)

> New here? Follow the end-to-end user walkthrough in
> [getting-started.md](getting-started.md) (account → ntfy → source → search →
> first notification).

### Without Docker

`just dev` runs the API (uvicorn `--reload` on :8000) and the frontend (vite on
:5173) against a Postgres and Redis you supply yourself. Point `POSTGRES_HOST`
and `REDIS_HOST` at `localhost` in `.env` first; the committed `.env.example`
uses the compose service names `db` and `redis`, which only resolve inside
Docker.

The pipeline runs separately, and is only needed to exercise scraping or
scheduling. From `backend/`, with the virtualenv:

```bash
.venv/bin/celery -A app.worker.celery_app:celery_app worker
.venv/bin/celery -A app.worker.celery_app:celery_app beat
```

Beat enqueues due searches every `SCHEDULER_TICK_SECONDS`. The worker writes
`celerybeat-schedule.db` and `dump.rdb` under `backend/`; both are ignored and
must not be committed.

## Accounts

- Multi-user with JWT; everyone has isolated data. Register in the UI; the
  **first** account created becomes the admin.
- `just seed` creates a demo account (`SEED_USER_EMAIL` / `SEED_USER_PASSWORD`)
  that owns the example source/target/search.
- Secrets `JWT_SECRET` and `CREDENTIALS_SECRET_KEY` must be set to real random
  values in any non-local deployment. The app **refuses to start** when
  `ENVIRONMENT` is anything other than `local`/`test` and either secret is still
  the built-in placeholder (forgeable tokens / decryptable credentials), or when
  `CREDENTIALS_SECRET_KEY` is shorter than 32 characters. Prefer a
  `Fernet.generate_key()` value (or `openssl rand -hex 32`). To rotate the
  credentials key without bricking stored ciphertext, set the old value as
  `CREDENTIALS_SECRET_KEY_PREVIOUS` while the new value is
  `CREDENTIALS_SECRET_KEY` (MultiFernet decrypt); re-saving credentials
  re-encrypts under the new primary.
## Receiving notifications

1. Install the **ntfy** app (iOS/Android) or open <https://ntfy.sh> in a browser.
2. Subscribe to the topic in your `.env` (`NTFY_DEFAULT_TOPIC`) or the topic set
   on your notification target in the UI.
3. Create a search; when a new matching job appears you'll get a push with the
   job title and a tap-through link.

To run fully offline, start the bundled ntfy server:
`docker compose --profile offline up -d ntfy` and point your target at
`http://localhost:8090`.

## Database

- Apply migrations: `just migrate`
- Create a migration after model changes: `just makemigration "..."`
- Open a psql shell: `docker compose exec db psql -U headstart`

## Common issues

| Symptom                              | Likely cause / fix                                       |
| ------------------------------------ | -------------------------------------------------------- |
| Redirected to login / 401s           | Access token expired and refresh failed; sign in again    |
| Redirected to `/verify-email` / 403  | Email not verified; check inbox, or API logs for the URL in local/test when `SMTP_HOST` is empty |
| No notifications arriving            | Wrong/unsubscribed ntfy topic; check `delivery_log`      |
| Search never runs                    | Search disabled, or `next_run_at` in the future          |
| Worker idle                          | Redis not reachable; check `just logs`                   |
| Auto-apply stuck on `queued`         | Celery worker not running; live apply is async, so start the worker (see [worker.md](modules/worker.md)) |
| Duplicate notifications              | Should not happen. Inspect `seen_job` uniqueness.        |
| DB connection errors on boot         | Run `just migrate`; ensure `db` healthy (`just ps`)      |
| `docker-credential-*.exe ... not found` on build/up | WSL credential-helper quirk; see [Windows / WSL](#windows--wsl) (`DOCKER_CONFIG=/tmp/dockercfg`) |

## Email (password reset & verification)

Both flows use the same `SMTP_*` env vars (see `.env.example`). In `local`/`test`,
when `SMTP_HOST` is empty the API logs the reset or verification URL at INFO, so
grep API logs for the link. Outside those environments `SMTP_HOST` is required
at startup and the log fallback never emits the token.

## Debugging the pipeline

- Inspect what a scraper returns without sending: run its unit test or call the
  service in a `python` shell inside the worker container.
- `delivery_log` records every send attempt with status and error.
- Logs are JSON by default (`LOG_FORMAT=json`); filter by `request_id` or
  `search_id` (when present in the message/extras) to follow one request or
  search end-to-end. Use `LOG_FORMAT=text` only for local grepping.

## Local application agent (dev-only)

**Do not enable on hosted multi-tenant production.** The inbox pipeline reads
recruiter email, classifies replies, routes folders, drafts follow-ups, detects
ghosted applications, and alerts when an interview needs scheduling. It requires
direct mailbox access and is gated by `INBOX_AGENT_ENABLED` (default `false`). See
[adr/0011-inbox-dev-only.md](adr/0011-inbox-dev-only.md).

Subsystem detail: [modules/inbox.md](modules/inbox.md). Apply + profile:
[modules/appliers.md](modules/appliers.md), [modules/profile.md](modules/profile.md).

### Prerequisites

- HeadStart running locally with **Celery worker and beat** (not API-only). With
  Docker: `just up` includes worker + beat. Native dev: start worker and beat in
  separate terminals (see [Without Docker](#without-docker)).
- `INBOX_AGENT_ENABLED=true` in `.env` (restart API + worker after changing).
- A mailbox: per-user credentials in **Settings → Inbox**, Gmail, Outlook, Yahoo OAuth,
  Fastmail API token, or env fallback for single-user dev (`INBOX_USE_ENV_CREDENTIALS=true` + `INBOX_*`
  vars in `.env.example`).
- Optional offline LLM: `LLAMACPP_MODEL_PATH=/path/to/model.gguf just llamacpp`,
  then set AI purposes to `llamacpp` in **Settings → AI models** (or rely on
  `heuristic` adapters with no local server).

### Mailbox setup (pick one)

| Path | When to use |
| ---- | ----------- |
| **Settings → Inbox** (IMAP/SMTP) | Multi-user local dev; credentials encrypted per user |
| **Gmail OAuth** | Gmail users; set `GMAIL_OAUTH_CLIENT_ID`, `GMAIL_OAUTH_CLIENT_SECRET`, `GMAIL_OAUTH_REDIRECT_URI`, then **Connect Gmail** in Settings |
| **Outlook OAuth** | Outlook / Microsoft 365; set `OUTLOOK_OAUTH_*` env vars, register Azure app (see [modules/inbox.md](modules/inbox.md#outlook-adapter)), then **Connect Outlook** in Settings |
| **Yahoo OAuth** | Yahoo Mail; set `YAHOO_OAUTH_*` env vars, register Yahoo app (see [modules/inbox.md](modules/inbox.md#yahoo-adapter)), then **Connect Yahoo** in Settings |
| **Fastmail API token** | Fastmail JMAP; create a Mail + Submission API token in Fastmail settings, then save in Settings → Inbox (see [modules/inbox.md](modules/inbox.md#fastmail-adapter)) |
| **Env fallback** | Single-user quick start; `INBOX_USE_ENV_CREDENTIALS=true` and all `INBOX_IMAP_*` / `INBOX_SMTP_*` vars |

Test connectivity: **Settings → Inbox → Test connection**, or
`POST /api/v1/inbox/test` (auth required).

### What beat runs when enabled

| Beat task | Default interval | Purpose |
| --------- | ---------------- | ------- |
| `process_inbox_messages` | 300s (`INBOX_POLL_INTERVAL_SECONDS`) | Poll mail, application-scoped gate, classify, route, ghost recovery, interview handoff |
| `detect_ghosted_applications` | 3600s (`INBOX_GHOST_CHECK_INTERVAL_SECONDS`) | Self-email when no recruiter reply after `INBOX_GHOST_WINDOW_DAYS` (default 14) |
| `process_pending_replies` | 60s (`INBOX_REPLY_SEND_INTERVAL_SECONDS`) | SMTP-send due auto-replies (only when `auto_reply_enabled` on routing config) |

Batch size per poll: `INBOX_POLL_BATCH_SIZE` (default 50). See
[modules/worker.md](modules/worker.md).

### End-to-end smoke test

1. **Profile & apply path.** Fill [application profile](modules/profile.md);
   enable `auto_apply_enabled` on a supported source; run a search or apply from
   **Jobs** so `application_log` has a baseline.
2. **Mailbox.** Save inbox credentials, connect Gmail, Outlook, Yahoo, or Fastmail;
   confirm **Test connection** succeeds.
3. **Inbound mail.** From another account, send a reply that references the
   employer domain or thread; wait for the next poll tick, or classify manually
   via `POST /api/v1/inbox/classify`.
4. **Verify.** Open `/app/applications` for pipeline stage; check
   `GET /api/v1/inbox/classifications` for label + routing status.
5. **Draft reply (optional).** Call `POST /api/v1/inbox/draft-reply` or use **Draft
   reply** on the applications page; preview before enabling auto-send.

### Safety defaults

- `auto_reply_enabled` is **off** by default on routing config, so drafts preview
  immediately; SMTP send waits for `INBOX_REPLY_MIN_DELAY_SECONDS` + jitter only
  after opt-in.
- Safe-send: legal/HR topic blocklist, hourly/daily caps (`INBOX_REPLY_MAX_PER_*`),
  audit log at `GET /api/v1/inbox/reply-send-logs`.
- Unrelated personal mail is skipped by `InboxGateService` before any LLM call.

### Common issues

| Symptom | Likely cause / fix |
| ------- | ------------------ |
| Inbox APIs return 403 / "not enabled" | `INBOX_AGENT_ENABLED` not `true`, or API not restarted after `.env` change |
| Settings has no Inbox card | Same cause: flag off; `GET /meta` shows `inbox_agent_enabled` |
| Mail never classifies | Worker/beat not running; poll interval not elapsed; message failed application gate (unrelated sender) |
| Gmail OAuth redirect fails | `GMAIL_OAUTH_REDIRECT_URI` must match Google Cloud console and API base URL |
| Outlook OAuth redirect fails | `OUTLOOK_OAUTH_REDIRECT_URI` must match Azure app registration redirect URI and API base URL |
| Yahoo OAuth redirect fails | `YAHOO_OAUTH_REDIRECT_URI` must match Yahoo app redirect URI and API base URL |
| Classifications work but no folders | Routing disabled or `out_of_scope` label; check `GET /inbox/routing` |
| Auto-replies never send | `auto_reply_enabled` off, delay not elapsed, or safe-send blocked; check reply-send logs |

## Deployment (AWS)

First-time deploy: **[deploying-to-aws.md](deploying-to-aws.md)** (step-by-step).
Architecture and Terraform layout: [modules/deployment.md](modules/deployment.md).

Ongoing code deploys (after infrastructure exists):

```bash
export AWS_REGION=us-east-2
export ECR_REGISTRY="<account-id>.dkr.ecr.us-east-2.amazonaws.com"
export ECS_CLUSTER=headstart-beta
just deploy
```

Migrations run as a one-off ECS task on each deploy.
