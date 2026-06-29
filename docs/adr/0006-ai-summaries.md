# 0006. AI match summaries in notifications

- **Status:** Accepted
- **Date:** 2026-06-29

## Context

Notifications listed a job's title/company/location/URL but never said *why* a
posting matched the user's search. Phase 5 of the roadmap calls for a short
"why this matches" blurb. We needed this to:

- work with no external dependency by default (CI, local, self-host),
- optionally use an LLM for richer text,
- reach every notification channel and the in-app Jobs feed, and
- never block or fail a notification if generation goes wrong.

## Decision

Introduce a third pluggable subsystem, `app/summarizers/`, mirroring the
scraper/notifier registry pattern: a `Summarizer` base class plus
`@register_summarizer("key")` adapters resolved via `get_summarizer`.

- Two providers ship: `heuristic` (offline default, builds the blurb from the
  search's own filters) and `openai` (opt-in, Chat Completions per job).
- A thin `SummaryService` (services layer) gates on config, picks the provider,
  truncates, and **swallows all provider errors** so summaries are best-effort.
- The blurb rides on `JobPosting.summary` through the pipeline and is persisted
  on `seen_job.summary`, so it is available to digests, the Jobs feed, and RSS.
- The pipeline generates summaries only for postings it will actually notify,
  right after cross-search dedup and before persisting/notifying.

## Consequences

- Every notifier renders the blurb when present; empty blurbs change nothing, so
  existing behavior and tests are preserved.
- Adding an AI provider is a one-file change; no branching on provider name.
- Storing the blurb on `seen_job` cost one nullable column + one migration and
  keeps digest reconstruction trivial.
- `summary` is presentational and intentionally excluded from `content_hash`, so
  it never affects dedup.

## Alternatives considered

- **Generate in each notifier** — would duplicate work per channel and re-call
  the model for digests. Rejected; generate once in the pipeline.
- **Don't persist; pass only in-memory** — digests (which rebuild postings from
  `seen_job`) and the Jobs feed would lose the blurb. Rejected.
- **Hard-code an OpenAI dependency** — breaks offline/CI use and forces an API
  key. Rejected in favor of a registry with an offline default.
