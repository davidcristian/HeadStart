# AGENTS.md

Operating manual and **strict constraints** for anyone working in this
repository. These rules exist to keep the codebase clean, modular, and cheap to
reason about as it grows.

If a rule here conflicts with a request, **follow the rule and say so**.

---

## 0. The prime directive: start from the docs

Any change should need only a small, well defined slice of the system in view.
The module boundaries and the docs exist to make that possible.

1. **Read [`docs/README.md`](docs/README.md) first.** It is a map. Use it to
   open only the one or two specific docs you need.
2. **Do not read the whole codebase** to make a change. Needing to is a signal
   that a boundary is missing or wrong; fix the boundary.
3. **Update docs in the same change that changes behavior.** Docs are part of
   the Definition of Done, not an afterthought. Stale docs are a bug.

---

## 1. Where code goes (module boundaries)

The backend is layered. Respect the direction of dependencies: **outer layers
depend on inner layers, never the reverse.**

```
api (routers)  ->  services  ->  repositories  ->  models / db
                      |
                      ├─► scrapers    (pluggable adapters)
                      ├─► notifiers   (pluggable adapters)
                      ├─► summarizers (pluggable adapters)
                      └─► + the other adapter families listed below
```

| Layer            | Path                       | Responsibility                                   | May import                          |
| ---------------- | -------------------------- | ------------------------------------------------ | ----------------------------------- |
| Routers          | `backend/app/api/`         | HTTP only: parse, validate, call a service       | services, schemas, core             |
| Services         | `backend/app/services/`    | Business logic / orchestration                   | repositories, scrapers, notifiers, summarizers, schemas, core |
| Repositories     | `backend/app/repositories/`| All DB access (queries)                          | models, core                        |
| Models           | `backend/app/models/`      | SQLAlchemy ORM tables                            | core                                |
| Schemas          | `backend/app/schemas/`     | Pydantic request/response/DTOs                   | (stdlib + pydantic only)            |
| Scrapers         | `backend/app/scrapers/`    | Fetch + normalize postings from a site           | schemas, core                       |
| Notifiers        | `backend/app/notifiers/`   | Deliver notifications to a channel               | schemas, core                       |
| Summarizers      | `backend/app/summarizers/` | "Why this matches" blurb generators              | schemas, core                       |
| Other adapter families | `backend/app/{appliers,cover_letters,email_classifiers,reply_drafters,resumes,portals,inbox}/` | Same base + `adapters/` + registry pattern, one family per concern | schemas, core |
| AI plumbing      | `backend/app/ai/`          | Shared LLM helpers/registry for the AI-backed families | core                          |
| CLI              | `backend/app/cli/`         | Small operational CLIs (seeding)                 | models, core                        |
| Core             | `backend/app/core/`        | Config, logging, db session, security (JWT/bcrypt), crypto (Fernet) | (framework + stdlib)                |

**Hard rules:**

- Routers MUST NOT touch the database directly. Go through a service ->
  repository.
- Business logic MUST NOT live in routers or repositories. It lives in services.
- Cross-cutting modules (scrapers, notifiers) are reached **only through their
  base interface + registry** (see §2). Never import a concrete adapter by name
  from a service.
- **Multi-user isolation is mandatory.** Owned entities (`source`, `search`,
  `notification_target`, `site_credential`) carry a `user_id`. Every API route
  requires `get_current_user` and scopes data to that user; services take a
  `user_id` and must never return another user's rows. See
  [`docs/modules/auth.md`](docs/modules/auth.md).

---

## 2. Extending the system (the modular contract)

Adding capability should mean **adding a file, not editing many**.

- **New job site →** add one adapter in `backend/app/scrapers/adapters/`,
  decorated with `@register_scraper("key")`. Nothing else changes.
- **New notification channel →** add one adapter in
 `backend/app/notifiers/adapters/`, decorated with `@register_notifier("key")`.
- **New AI summary provider →** add one adapter in
 `backend/app/summarizers/adapters/`, decorated with `@register_summarizer("key")`.

Follow the exact recipes in [`docs/recipes.md`](docs/recipes.md).
Both subsystems use a base abstract class + a registry; you implement the base
class and self-register. Do not add `if adapter == "x"` branching anywhere.

---

## 3. File & function hygiene

- **One responsibility per file.** Soft cap **~300 lines**; if you exceed it,
  split. A router file should map to one resource. The cap targets **source**
  modules (it keeps each module focused and boundaries clear); **test files are
  exempt** because a test file already maps to one module and grows with its
  cases. `scripts/check_loc.sh` skips `backend/tests/`, `frontend/src/test/`
  (vitest helpers), and `*.test.ts(x)`, but not every path segment named
  `tests/`. Still split a test file when a genuinely distinct concern deserves
  its own file.
- Prefer pure functions and small classes. Side effects (I/O, network, DB) live
  at the edges (repositories, scrapers, notifiers), not in the middle.
- Public functions get **type hints** and a one-line docstring describing intent
  (the *why*), not a restatement of the code.
- **No narrating comments.** Comments explain trade-offs, constraints, or
  non-obvious intent only.

---

## 4. Always run things via `scripts/`

Never invent ad-hoc commands. Local dev, CI, and deployment all call the same
scripts so behavior is identical everywhere.

| Task             | Command                          |
| ---------------- | -------------------------------- |
| Install toolchains | `just setup`                   |
| Lock backend deps | `just lock-backend`             |
| Run full stack   | `just up` / `just down`          |
| Run tests        | `just test`                      |
| Lint             | `just lint`                      |
| Format           | `just format`                    |
| Type-check       | `just typecheck`                 |
| Full gate        | `just check`                     |
| DB migration     | `just migrate` / `just makemigration "..."` |
| Seed example data| `just seed`                      |
| Deploy to AWS    | `just deploy`                    |

The justfile has further build/deploy/ops recipes (`build`, `push`, `dev`,
`logs`, the `aws-*` helpers, …). Bare `just` lists everything; the table above
is the everyday loop.

If you need a new operation, add a script under `scripts/` and a `just` recipe.
Do not document a raw command for others to copy-paste.

---

## 5. Definition of Done (every change)

A change is complete only when **all** of the following hold:

1. `just check` passes (lint + typecheck + tests) locally.
2. New behavior has tests. Bug fixes add a regression test.
3. Relevant docs updated (`docs/modules/*`, and an ADR if a decision was made).
4. No secrets committed. Config comes from env vars (see `.env.example`).
5. Commit messages follow **Conventional Commits** (`feat:`, `fix:`, `docs:`,
   `refactor:`, `test:`, `chore:`, `ci:`, `build:`) and cite nothing that can be
   deleted: no tracker ids, phase/batch numbers, roadmap references, PR numbers,
   or em/en dashes. `scripts/check_commit_msg.sh` enforces this on commit and in
   CI; the reasoning is in [`docs/conventions.md`](docs/conventions.md).
6. The change is **scoped**: one logical concern per PR. Split unrelated work.

---

## 6. Quality bars

- **Backend:** `ruff` (lint) + `black` (format) + `mypy` (types, strict-ish) +
  `pytest`. **Coverage is gated at 100%**. Pytest runs with `--cov --cov-branch`
  and `fail_under = 100` (see `backend/pyproject.toml`). Every reachable line and
  branch must be tested; only genuinely unexecutable code is excluded
  (`TYPE_CHECKING`, `@abstractmethod`). Do not add per-line `# pragma: no cover`.
- **Migrations:** unit tests run on SQLite, so raw SQL in migrations must also
  work on Postgres (the production dialect). `just test-migrations` applies
  every migration from scratch to a disposable dockerized Postgres; CI runs it
  on every push. See the migration recipe in
  [`docs/recipes.md`](docs/recipes.md).
- **Frontend:** `eslint` + `tsc --noEmit` + `prettier` + `vitest`. **Coverage is
  gated at 100%** on statements, branches, functions and lines (see the
  `test.coverage.thresholds` in `frontend/vite.config.ts`); `npm test` runs
  `vitest run --coverage`. Excluded from the gate (see `coverage.exclude` in
  that config): `src/types/**`, `**/*.d.ts`, `**/*.test.{ts,tsx}`,
  `src/main.tsx`, and `src/test/**`.
- New/changed code must keep both gates at 100%; a `just check` that drops below
  100% coverage fails.
- Pre-commit hooks enforce formatting and linting; do not bypass them
  (`--no-verify` is forbidden unless the user explicitly asks).

---

## 7. Security & safety

- Secrets only via env / AWS Secrets Manager. Never hardcode tokens, never log
  them.
- Validate and normalize all external input (scraped HTML/JSON is untrusted).
- Be a polite scraper: respect intervals, set a real User-Agent, handle rate
  limits and failures gracefully. Do not add aggressive retry storms.
- Destructive infra actions (`terraform destroy`, DB drops) require explicit
  human confirmation.

---

## 8. Git & PR conventions

- Branch names: `feat/...`, `fix/...`, `docs/...`, `chore/...`.
- Keep PRs small and reviewable. A green `just check` is the entry ticket.
- Never force-push shared branches; never commit `.env` or `*.tfvars`.

---

## 9. Quick links

- Documentation map: [`docs/README.md`](docs/README.md)
- Architecture: [`docs/architecture.md`](docs/architecture.md)
- Conventions: [`docs/conventions.md`](docs/conventions.md)
- Extension recipes: [`docs/recipes.md`](docs/recipes.md)
- Operations: [`docs/runbook.md`](docs/runbook.md)
- Decisions: [`docs/adr/`](docs/adr/)

---

## 10. Working style

- **Claims carry evidence.** Never report a gate green without having run it in
  this session; show the command and result. Unverified statements are labeled
  assumptions.
- **Distrust green.** After wiring or changing a gate, prove it can fail.
  Introduce a violation, watch it fail, remove it. An unfalsifiable gate is
  worse than none.
- **Read before you write.** Open the file and its call sites before editing;
  never edit from memory of its contents or invent an API. Check the
  signature.
- **Report faithfully.** Failing tests are reported with their output; skipped
  steps are named. A wrong "done" costs more than an honest "not yet".
- **Stop when surprised.** When output contradicts your model of the system,
  re-derive from evidence. Don't pattern-match to the nearest familiar failure
  and push through.
