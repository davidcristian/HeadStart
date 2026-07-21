# Conventions

The non-negotiables live in [AGENTS.md](../AGENTS.md). This file fills in the
day-to-day details.

## Python (backend)

- Python 3.12. Formatting by **black**, linting by **ruff**, types by **mypy**.
- Line length 100.
- Naming: `snake_case` for functions/variables, `PascalCase` for classes,
  `UPPER_SNAKE` for constants.
- Imports are grouped and sorted (ruff isort): standard lib, third-party, local.
- Use type hints everywhere. Prefer `from __future__ import annotations` is not
  needed on 3.12 for built-in generics.
- Pydantic v2 for all schemas and settings. SQLAlchemy 2.0 typed ORM
  (`Mapped[...]`, `mapped_column(...)`).
- **Synchronous by design.** The persistence layer, services, scrapers, and
  notifiers are all synchronous. FastAPI routes are plain `def` (FastAPI runs
  them in a threadpool), and Celery tasks call the same services directly. This
  keeps one execution model across API and worker with no async/await and no
  event-loop juggling. That is the right trade-off for an I/O-light polling
  workload.
  HTTP uses `httpx.Client`; the optional Playwright scraper uses its sync API.

### Layering (enforced)

Outer depends on inner only: `api -> services -> repositories -> models`.
Scrapers and notifiers are reached only via their base class + registry. See the
table in [AGENTS.md](../AGENTS.md) §1.

### Errors

- Raise domain exceptions from services (`app/core/exceptions.py`); routers map
  them to HTTP responses via the handlers in `app/main.py` (`NotFoundError`→404,
  `ValidationError`→400, `ConflictError`→409, `UnauthorizedError`→401,
  `PlanLimitError`→402 with `code`/`plan`/`limit`, `RateLimitError`→429). Never
  re-raise `HTTPException` for those cases in a router, because that bypasses
  the shared body shape. Never leak raw DB/driver errors to clients.
- Scrapers and notifiers must not crash the worker: wrap external I/O and surface
  failures as logged, recorded errors.

## TypeScript (frontend)

- Strict mode on. Formatting by **prettier**, linting by **eslint**.
  `just lint --frontend` (and CI) runs `npm run format:check` so prettier
  drift fails the gate the same way `black --check` does for the backend.
- Functional components + hooks. Server state via **TanStack Query** hooks in
  `src/hooks/` (`queries.ts` / `mutations.ts`), which wrap the typed API client
  in `src/api/`. Components do not call `api.*` directly. Keep business logic
  out of components and in hooks/helpers.
- Types for API payloads live in `src/types/` and mirror the backend schemas.

## Commits & branches

- **Conventional Commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`,
  `chore:`, `ci:`, `build:`. No other type. `style:` is `chore:`; an
  accessibility fix is `fix:`.
- Branches: `feat/...`, `fix/...`, `docs/...`, `chore/...`.
- One logical concern per PR. `just check` must pass before opening a PR.

### Write for the reader in two years

A commit message outlives every tracker, board and plan it might cite, and it
cannot be corrected later without rewriting history and forcing a re-clone. So
it must stand on its own.

- **No pointers to things that can vanish.** No tracker ids (`FRO-07`, `WS26`),
  no `Phase 3`, no `batch 8`, no roadmap or backlog references. Say what the
  change does. A tracker was deleted once and left 985 dangling ids behind.
- **No PR references.** No `(#123)` suffix, no `PR #45`. The host's squash merge
  appends `(#N)` on its own, so clear it from the message box when merging.
- **No em or en dashes.** Restructure the sentence; do not swap in a comma or a
  colon and call it done.

`scripts/check_commit_msg.sh` enforces this as a `commit-msg` hook and in CI.

### Dashes in code

The same no-dash rule applies to source, docs and product copy, with one
exception: text we **match or parse from someone else** keeps the character
verbatim. Job boards title pages `"Software Engineer — Google Careers"` and
postings write `"$120K – $180K"`, so the matchers, the salary regex and the
captured fixtures they read must not be tidied. `scripts/check_text.sh` holds
the allowlist; add to it only with a reason, since an over-broad entry silently
reopens the rule.

Spelling a dash as `\u2014` to satisfy the grep is not compliance: the dash
still reaches the user. The gate rejects the escape too.

## Testing

- Backend: `pytest`. Unit-test services, scrapers (against saved fixtures), and
  notifiers (mocked HTTP). Integration-test the worker pipeline.
- Scraper tests must not hit the network. Use fixtures under
  `backend/tests/fixtures/`.
- Frontend: `vitest` + Testing Library for components and hooks.

## File size

- Soft cap of **~300 lines per source file** (see [AGENTS.md](../AGENTS.md) §3).
  `just lint` runs `scripts/check_loc.sh` and fails when any `.py`/`.ts`/`.tsx`
  file exceeds 300 lines. The exclusions are `alembic/versions/`,
  `backend/tests/` only (not any nested `…/tests/` under app code),
  `frontend/src/test/` vitest helpers, and `*.test.ts(x)`. Offender paths are
  printed relative to the repo root via a literal prefix strip (`[[ == ]]` +
  `${file:${#prefix}}`), not `${file#${REPO_ROOT}/}`, so a checkout path
  containing glob metacharacters (`*?[]`) cannot garble the report.

## Configuration

- All config via environment variables, parsed by `app/core/config.py`
  (pydantic-settings). Document every new variable in `.env.example`.
- No magic numbers in code that should be tunable. Promote them to settings.
