# Module: Worker & Scheduler

**Path:** `backend/app/worker/`

Celery provides the scheduler (beat) and the workers. The worker package is
**glue only** — it calls services; business logic lives in services.

## Pieces

- `celery_app.py` — the Celery application + config (broker/result backend from
  settings).
- `schedule.py` — the beat tick: find due searches and enqueue them.
- `tasks.py` — `run_search(search_id)`: the per-search pipeline.

## Due-based scheduling with catch-up

Beat runs every `SCHEDULER_TICK_SECONDS`. On each tick (and once on startup) it:

1. Selects searches where `enabled = true AND next_run_at <= now`.
2. Enqueues `run_search` for each.

Each search carries `interval_seconds`, `last_run_at`, `next_run_at`.

After a run, the worker sets `last_run_at = now` and
`next_run_at = now + interval_seconds`.

**Catch-up:** if the host was asleep/offline, many searches will be overdue on
the next tick. They each run **once** (not once per missed interval) because
`next_run_at` is recomputed from *now*, not advanced N times. `SCHEDULER_MAX_CATCHUP`
documents/limits this collapse. Dedup via `seen_job` means a missed window only
delays notifications; nothing is dropped or duplicated.

```mermaid
flowchart TD
  tick["beat tick (every N s)"] --> q{"search.next_run_at <= now\nand enabled?"}
  q -->|yes| enqueue["enqueue run_search(id)"]
  q -->|no| skip[skip]
  enqueue --> scrape[scrape] --> filter[apply search filters]
  filter --> dedupe[dedupe vs seen_job]
  dedupe --> cross{"URL seen in another\nsearch for user?"}
  cross -->|yes| record_only[record seen_job only]
  cross -->|no| notify["notify new jobs"]
  record_only --> reschedule
  notify --> record["write seen_job + delivery_log"]
  record --> reschedule["last_run_at=now; next_run_at=now+interval"]
```

## Pipeline (`run_search`)

1. Load the search + its source + target (service).
2. Resolve and run the scraper (`get_scraper(source.adapter_key).fetch(ctx)`).
3. Apply the search's `filters` JSON to drop non-matching postings.
4. Dedupe postings against `seen_job` for that search (by `external_id`).
5. Skip notification when the normalized job URL was already seen in any of the
   owner's other searches (cross-search dedup); still persist a `seen_job` row for
   this search so the Jobs feed stays complete.
6. Send remaining new postings via `get_notifier(target.type).send(ctx, new_jobs)`.
7. Persist `seen_job` rows and `delivery_log` entries; update schedule fields.

Failures at any external step are caught, logged, and recorded; the worker keeps
running.

## Testing

- Integration test drives the full pipeline against scraper fixtures + a fake
  notifier, asserting only-new jobs notify and dedup holds.
- A downtime/catch-up test sets `next_run_at` in the past and asserts a single
  catch-up run.
