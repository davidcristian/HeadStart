# 0012. Hashed backend dependency lockfiles

- **Status:** Accepted
- **Date:** 2026-07-04

## Context

Backend runtime and optional extras were declared only as open lower bounds in
`backend/pyproject.toml` (`fastapi>=0.111`, …) with no committed lockfile.
`pip install -e backend` and the Docker image therefore resolved whatever PyPI
served that day, so CI and production images could silently diverge.
The frontend already pins via `package-lock.json`.

## Decision

Commit pip-tools lockfiles with hashes under `backend/`:

- `requirements.txt` covers runtime
- `requirements-dev.txt` covers runtime plus the `dev` extra
- `requirements-playwright.txt` covers runtime plus the `playwright` extra

`pyproject.toml` keeps human-editable `>=` floors. Those floors must track the
majors CI actually tests via the lockfiles. Do not advertise an older major the
suite never runs. Builds install from the lockfiles
(`--require-hashes`), then install the local package with `--no-deps`.
Regenerate with `just lock-backend` whenever floors or extras change.

## Consequences

- Docker, CI, and `just setup` share the same resolved versions.
- Dependency bumps are explicit diffs in the lockfiles.
- Operators must run `just lock-backend` (and commit) after editing
  `pyproject.toml` dependencies; forgetting leaves CI/Docker on stale pins
  until the lock is refreshed.

## Alternatives considered

- **uv lock / Poetry.** Also fine; pip-tools matches the existing pip-based
  Dockerfile and CI without adding a second package manager.
- **Upper caps only in pyproject.** Still non-reproducible across patch
  releases and does not pin transitive deps.
- **Lock runtime only.** Leaves CI tooling and Playwright unpinned; we lock
  all three install surfaces that the repo actually builds.
