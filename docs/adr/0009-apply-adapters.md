# 0009. Pluggable apply adapters and Greenhouse first slice

- **Status:** Accepted
- **Date:** 2026-07-01

## Context

[Phase 7 — Auto-apply](../roadmap.md) needs to submit applications per job board.
Each ATS has a different apply flow. [ADR-0008](0008-application-profile.md) added
encrypted profile storage; the next step is a registry of apply adapters plus
minimal orchestration so future UI and worker paths can call one service.

## Decision

- Add `backend/app/appliers/` with the same base-class + registry pattern as
  scrapers and notifiers. The adapter `key` matches `source.adapter_key` when
  that site supports auto-apply.
- Introduce `ApplyContext` / `ApplyResult` and `ApplyService.apply_to_job`,
  which loads the user's profile, optional site credential, and merged source
  config, then delegates to `get_applier(key)`.
- Ship **Greenhouse** first: map `ProfileData` to the Job Board API JSON POST.
  Support `dry_run` to preview payloads without a network call. Live submission
  requires a per-board Job Board API key in config or credential
  `session.job_board_api_key` (employer-issued; encrypted when stored as a
  credential).
- On successful live submit, set `seen_job.status` to `applied`. API routes,
  Jobs UI, queued workers, consent gates, and audit logs remain later Phase 7
  items.

## Consequences

- Adding a board means one adapter file + tests; no branching on adapter name in
  services.
- Greenhouse live apply is limited to boards where the user (or operator) has a
  Job Board API key; dry-run still helps preview and future browser-based apply.
- `ApplyService` is the single seam for routers, workers, and tests.

## Alternatives considered

- **Browser-only apply (Playwright) for v1** — works without employer API keys
  but is harder to test and more brittle; defer as a complement to API adapters.
- **Apply logic inline in `JobService`** — violates module boundaries and makes
  per-site extension painful; rejected.
