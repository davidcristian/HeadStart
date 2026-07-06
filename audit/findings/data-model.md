# Data model — ORM models, repositories, migrations

This area covers the persistence layer: SQLAlchemy ORM models (`backend/app/models/`), the repository layer that owns all DB access (`backend/app/repositories/`), and the Alembic migrations that shape the schema. The headline finding is a **high-severity privilege-escalation path**: deleting the bootstrap admin nulls the registration lock and auto-promotes the next registrant to admin. Beyond that, the audit found a cluster of **unbounded / unindexed query patterns** in the scrape and ghost-detection hot paths that degrade linearly with account age, two **GDPR retention gaps** where erased users' email/IP survive account deletion, and several lower-severity model/migration drift and cascade-consistency issues.

**Summary by severity:** 🔴 critical: 0 · 🟠 high: 1 · 🟡 medium: 5 · ⚪ low: 8 (14 findings after merging 4 duplicate pairs).

---

<a id="dat-01"></a>
### DAT-01 — Deleting bootstrap admin resets registration lock, auto-promoting next registrant to admin
🟠 **HIGH** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/8)) · Confidence: high (5/5 verifiers) · Effort: S · WS19

**Update (2026-07-09).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/8): `claim_bootstrap_admin` now gates on
`registration_lock.bootstrap_claimed` (permanent latch) instead of a nullable
`bootstrap_user_id`. Deleting the bootstrap user may still `SET NULL` the FK,
but the latch stays set so a later registrant is never auto-promoted.
Migration `0037_reg_lock_claimed` backfills `True` when an admin already exists
or the lock already points at a user.

**Locations:** `backend/app/repositories/users.py:37` (`UserRepository.claim_bootstrap_admin`); plus `backend/app/models/registration_lock.py:14`, `backend/alembic/versions/20260628_0008_registration_lock.py:34`, `backend/app/services/auth.py:68`.

**Evidence.** `claim_bootstrap_admin()` only matches rows where `bootstrap_user_id.is_(None)`, treating a NULL slot as "unclaimed". But the FK is declared `ondelete="SET NULL"`, so deleting the bootstrap admin's user row resets `bootstrap_user_id` back to NULL. On the next registration, `register()` re-claims the now-open slot and sets `is_admin=True` on a brand-new account. The delete guard (`auth_account.py:82`) only blocks deletion of the *last* admin, so a bootstrap admin who has a peer admin passes the guard and re-opens the slot.

**Failure scenario.** A second admin exists. The original bootstrap admin deletes their own account (the `count_admins > 1` guard passes). The `SET NULL` cascade reverts the registration lock to NULL. The very next self-service registrant is silently promoted to a full admin without any invitation or approval.

**Suggested fix.** Treat the bootstrap slot as permanently consumed once used — gate on "any admin exists" or a dedicated claimed flag that is never nulled — rather than tying the lock to a deletable user row via `SET NULL`.

**Verification.** Confirmed 5/5 adversarial verifiers. FK is `ondelete=SET NULL` (registration_lock.py:14) and `claim_bootstrap_admin` gates only on `bootstrap_user_id.is_(None)`; the delete guard (auth_account.py:82) only blocks the last admin, so a bootstrap admin with a peer admin can delete and re-open the slot, auto-promoting the next registrant.

---

<a id="dat-02"></a>
### DAT-02 — DataRequestLog retains user_email & IP indefinitely after account erasure
🟡 **MEDIUM** · 🔒 security · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: M · WS18

> Merged with DAT-10 (`data_request_log.py:22`, low/medium confidence, uid 250), which reports the same defect from the erasure-path angle. Combined here as one finding.

**Update (2026-07-10).** Fixed: account deletion redacts prior export audit rows for the user and writes the deletion row with an HMAC email pseudonym (`erased:<hex>`) and no IP/UA. Migration `0038_redact_data_req` redacts historical delete/orphaned rows. Privacy policy Retention section documents the post-erasure audit basis.

**Locations:** `backend/app/models/data_request_log.py:22` (`DataRequestLog.user_email`); plus `backend/app/services/auth_account.py:112` and the delete-row write at `auth_account.py:127`.

**Evidence.** On account deletion, `user_id` is `ondelete="SET NULL"`, but `user_email` (String 320, `nullable=False`) plus `ip_address` and `user_agent` persist indefinitely. `_record_data_request` writes the user's raw email into the delete audit row before `repo.delete(user)`, so the person's email and IP survive the very erasure they requested. A grep of the codebase shows only `add` / `list_recent` on this table — no purge or retention job exists anywhere.

**Failure scenario.** An erased user (GDPR Art.17 request) still has their email address and IP retained in `data_request_log` forever. A later subject-access or erasure request cannot remove them, there is no defined retention limit, and a future breach could re-disclose PII the user asked to be erased.

**Suggested fix.** Define a retention window with a purge job for audit rows, or hash/pseudonymize the `user_email` reference in the delete audit row; document the retention basis in the privacy policy.

**Verification.** Confirmed 3/3 adversarial verifiers (both merged records confirmed 3/3). `data_request_log.user_email` is NOT NULL and retained while `user_id` is SET NULL on delete; grep shows only add/list_recent with no purge job. Leans low because audit-log retention is a legitimate-basis record, but the retention gap is real.

---

<a id="dat-03"></a>
### DAT-03 — Missing indexes on seen_job.status/applied_at and application_log.dry_run
🟡 **MEDIUM** · ⚡ perf · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/61)) · Confidence: high (3/3 verifiers) · Effort: S · WS33

> Rolls up the missing-index pattern on `seen_job`. Near-duplicates DAT-11 (`seen_job.status` unindexed, low) and DAT-14 (ghost sweep full-scan, low) are kept as separate low-severity records below because each cites a distinct caller; this record is the broadest and covers both tables.

**Locations:** `backend/app/models/seen_job.py:36` (`SeenJob.status`); plus `backend/app/models/seen_job.py:40`, `backend/app/repositories/ghost_detection.py:20`, `backend/app/models/application_log.py:25`, `backend/app/repositories/applications.py:19`.

**Evidence.** `GhostDetectionRepository` filters `status == 'applied' AND applied_at <= cutoff AND ghosted_at IS NULL` over the entire `seen_job` table on every beat tick, but `status` and `applied_at` have no index — only `search_id` is indexed (`ix_seen_job_search_id`). Separately, the applications pipeline's distinct subquery filters `ApplicationLog.dry_run.is_(False)`, which is also unindexed.

**Failure scenario.** As `seen_job` grows to millions of rows, the periodic `detect_ghosted_applications` tick performs a full table scan on every run, and the applications-pipeline distinct subquery scans `application_log` — both degrading progressively with total history.

**Suggested fix.** Add a composite/partial index on `(status, applied_at)` (partial `WHERE ghosted_at IS NULL`), and consider an index on `application_log(dry_run, seen_job_id)`.

**Fix.** Models declare `ix_seen_job_status_applied_at_unghosted` (partial `(status, applied_at)` where `ghosted_at IS NULL`) and `ix_application_log_dry_run_seen_job_id` on `(dry_run, seen_job_id)`; Alembic revision `0042_seen_job_app_log_idx`.

**Verification.** Confirmed 3/3 adversarial verifiers. `seen_job` indexes only `search_id`; `status`/`applied_at`/`ghosted_at` and `application_log.dry_run` are unindexed, and `list_stale_applications` filters `status`/`applied_at` each ghost-detection tick, so a growing table triggers full scans.

---

<a id="dat-04"></a>
### DAT-04 — recent_failures_for_searches loads all failed deliveries, trims in Python (no SQL LIMIT)
🟡 **MEDIUM** · ⚡ perf · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: M · WS33

**Locations:** `backend/app/repositories/deliveries.py:361` (`DeliveryLogRepository.recent_failures_for_searches`). Note: cited line 361 is stale — the file is ~47 lines; the query is around lines 26-36. Symbol and evidence hold. Called from the search-status view (`searches.py:107`).

**Evidence.** The query `SELECT ... WHERE DeliveryLog.status == 'failed' ORDER BY sent_at DESC` has **no `.limit()`**. The per-search cap (`if len(bucket) >= limit: continue`) trims results in Python only *after* every failed row has already been materialized.

**Failure scenario.** A search that has accumulated thousands of failed deliveries causes the dashboard / search-status query to pull all failed `delivery_log` + `seen_job` rows into memory on each call, just to display the most recent 5.

**Suggested fix.** Push the per-search top-N into SQL (window function / lateral join / per-search `UNION` or `ROW_NUMBER()`), or at minimum cap the outer query; avoid materializing all failures.

**Verification.** Confirmed 5/5 adversarial verifiers. `deliveries.py` query has no `.limit()`; all failed deliveries for the searches are materialized and trimmed in Python; called from the search status view (`searches.py:107`). Line 361 is wrong (file is 47 lines) but the symbol and evidence hold.

---

<a id="dat-05"></a>
### DAT-05 — Cross-search dedup normalizes user's whole job-URL history in Python per scrape
🟡 **MEDIUM** · ⚡ perf · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: M · WS33

> Merged with DAT-06 (uid 268, `jobs.py:60`, same symbol, confirmed 3/3), which is the identical defect. Combined here as one finding.

**Locations:** `backend/app/repositories/jobs.py:60` (`SeenJobRepository.existing_normalized_urls_for_user`). Note: the alternate record cited line 839, which is stale; the real query is around lines 67-73. Called every scrape at `backend/app/services/pipeline.py:205`.

**Evidence.** `existing_normalized_urls_for_user` selects `SeenJob.url` for **all** of a user's searches (no limit, only `user_id` + `url != ''` filters), then computes `{normalize_job_url(url) for url in ...}` in Python. Because normalization is application-side, no index can help. It runs on every scrape just to intersect with the current batch's URLs, so cost is O(total jobs) per run regardless of batch size — and there is no upstream batch bound.

**Failure scenario.** An active user accumulates tens of thousands of seen jobs; every poll cycle transfers and re-normalizes their entire history, growing scrape latency and DB load unboundedly with account age rather than with how many new postings actually arrived.

**Suggested fix.** Persist an indexed `normalized_url` column written at insert time and intersect in SQL (`WHERE normalized_url IN (:batch)`), instead of normalizing the full history in Python per scrape.

**Verification.** Confirmed 5/5 adversarial verifiers (merged record DAT-06 confirmed 3/3). `jobs.py` selects all of a user's `seen_job.url` and normalizes in Python with no SQL filter by wanted URLs; called every scrape (pipeline.py:205), so latency grows unbounded with account history. The cited line 839 is stale but the symbol is correct.

---

<a id="dat-07"></a>
### DAT-07 — Erasure of artifacts/promos relies on DB-only FK cascade, untested (SQLite FK off)
🟡 **MEDIUM** · 🐞 bug · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: M · WS33

> Related to DAT-12 (low, `user.py:63`) which frames the same gap as a consistency issue with a broader table inventory. Kept separate because DAT-12 is scoped to the ORM-relationship convention; this record is the erasure/test-coverage bug. See DAT-12 below.

**Locations:** `backend/app/repositories/users.py:113` (`UserRepository.delete`); plus `backend/app/models/application_artifact.py:22`, `backend/app/models/promo_redemption.py:28`, `backend/app/models/promo_validation_attempt.py:15`, `backend/tests/conftest.py:60`.

**Evidence.** `application_artifact`, `promo_redemption`, and `promo_validation_attempt` all use `ondelete=CASCADE` on their FK to `user.id`, but none of them appear in `User`'s ORM relationships, so there is no ORM-level cascade. Tests use in-memory SQLite with no `PRAGMA foreign_keys=ON` (`conftest.py:60`), meaning FK cascade deletion is never exercised by the suite. `delete_user_account` calls `repo.delete(user)` with no manual child deletes.

**Failure scenario.** If any Postgres FK constraint is ever missing, deferred, or dropped by a future migration, deleting a user leaves orphaned encrypted resume artifacts and promo PII behind — and the test suite cannot catch it because SQLite silently ignores the FK.

**Suggested fix.** Add these tables to `User`'s ORM relationships with `cascade='all, delete-orphan'`, or add an explicit repo delete; and enable the SQLite `foreign_keys` pragma in tests, asserting child rows are gone after user deletion.

**Verification.** Confirmed 3/3 adversarial verifiers. The three tables have `ondelete=CASCADE` but are absent from `User` ORM relationships (user.py); `delete_user_account` calls `repo.delete(user)` with no manual deletes, and conftest sets no `PRAGMA foreign_keys=ON`, so the cascade is untested.

---

<a id="dat-08"></a>
### DAT-08 — Migration omits server_default for NOT NULL text cols that models declare default=''
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: S · WS33

**Locations:** `backend/alembic/versions/20260630_0031_inbox_reply_send_log.py:33` (`inbox_reply_send_log`).

**Evidence.** The `inbox_reply_send_log` model declares `reason` / `subject` / `body_excerpt` as `nullable=False, default=''`, but that is an ORM-only default. The migration creates these columns NOT NULL with **no** `server_default`. The sibling table `inbox_classification` (`reason` / `subject` / `from_addr`) *does* get a `server_default` in migration 0024, so the convention is applied inconsistently.

**Failure scenario.** Any non-ORM INSERT (raw SQL, a future backfill/data-migration, or external tooling) that omits these columns fails the NOT NULL constraint on Postgres, whereas the sibling columns would have defaulted cleanly.

**Suggested fix.** Add a matching `server_default=''` in the migration (as done for `inbox_classification`), or drop the ORM-only default; keep model and schema in sync.

**Verification.** Confirmed 3/3 adversarial verifiers. Model uses ORM `default=''` (lines 31-33) but migration 0031 creates the columns NOT NULL without `server_default`, while sibling migration 0024 does set `server_default=''` — real drift, low is fair.

---

<a id="dat-09"></a>
### DAT-09 — ApplicationLog.status comment omits queued/processing states the code stores
⚪ **LOW** · 📝 doc · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: XS · WS33

**Locations:** `backend/app/models/application_log.py:119` (`ApplicationLog.status`). Note: the comment is actually near line 24.

**Evidence.** The column comment reads `# submitted | dry_run | failed`, but `apply.py` sets `status='queued'` and `status='processing'`, and `application_logs.py:12` defines `_PENDING_STATUSES = ('queued', 'processing')` which filters on exactly those values.

**Failure scenario.** A developer trusting the model comment as the canonical status enum omits `queued`/`processing` handling, producing incorrect pipeline or triage logic.

**Suggested fix.** Update the comment to enumerate all persisted statuses (`queued` / `processing` / `submitted` / `dry_run` / `failed`), or reference a canonical constant.

**Verification.** Confirmed 3/3 adversarial verifiers. Comment reads 'submitted | dry_run | failed' but `apply.py` sets 'queued'/'processing' and `application_logs.py:12` `_PENDING_STATUSES` filters them — genuine doc-drift, low is fair.

---

<a id="dat-10"></a>
### DAT-10 — DataRequestLog retains user_email & IP indefinitely after account erasure (erasure-path view)
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: S · WS18

> This is the same underlying defect as DAT-02 (medium), reported from the account-erasure path. Retained here for traceability; see [DAT-02](#dat-02) for the primary write-up and merged treatment.

**Locations:** `backend/app/models/data_request_log.py:22` (`DataRequestLog`); plus `backend/app/services/auth_account.py:112`.

**Evidence.** The `user_id` FK is `ondelete="SET NULL"`, but `user_email` (String 320, `nullable=False`) plus `ip_address` / `user_agent` persist forever. `_record_data_request` writes `user.email` into the delete audit row, so after `repo.delete(user)` the person's email and IP survive the erasure they requested. No purge or retention job exists.

**Failure scenario.** A user who deletes their account (GDPR Art.17) still has email + IP retained in `data_request_log` indefinitely; a later breach or subject-access request re-discloses PII the user asked to be erased.

**Suggested fix.** Store a hashed/pseudonymized user reference in the delete audit row, or set a documented retention window with a purge job.

**Verification.** Confirmed 3/3 adversarial verifiers. `_record_data_request` writes `user.email` + IP into `data_request_log` with `user_id=None` for deletes; no purge/retention job exists, so email/IP survive account erasure indefinitely — real GDPR retention gap, low is fair given the legitimate audit-retention basis.

---

<a id="dat-11"></a>
### DAT-11 — seen_job.status has no index despite status-filtered queries in pipeline/ghost/sync paths
⚪ **LOW** · ⚡ perf · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: S · WS33

> Overlaps DAT-03 (medium) and DAT-14 (low) on the missing `seen_job` index theme; kept distinct because it inventories the full set of status-filtered callers and also flags `delivery_log.status`.

**Locations:** `backend/app/models/seen_job.py:842` (`SeenJob.status`). Note: the column is at line 36, not 842. Plus `backend/app/models/delivery_log.py:251`.

**Evidence.** The `status` column is un-indexed (grep shows no `create_index` on any status column across models or migrations). It is filtered in `jobs.list_all` (`status=`), `applications.list_jobs_for_user` (`status IN ...`), `ghost_detection` (`status == 'applied'`), and `sync_after_scrape`.

**Failure scenario.** As the `seen_job` dedup ledger grows to millions of rows, status-filtered reads (pipeline view, ghost-detection sweep, per-user job list) perform sequential scans, degrading API latency.

**Suggested fix.** Add an index on `seen_job.status` (or composite `(search_id, status)`); consider `delivery_log.status` too, used by admin_stats counts.

**Verification.** Confirmed 5/5 adversarial verifiers. `seen_job.status` (line 36, not 842) is unindexed; most callers scope by indexed `search_id`/`user_id` first, but `ghost_detection.py:24` filters `status == 'applied'` globally with no scoping index, so a periodic full seq scan is real — though "API latency" is overstated, making this low.

---

<a id="dat-12"></a>
### DAT-12 — Three user-owned tables cascade only via DB FK, no ORM relationship on User
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: S · WS33

> Same gap as DAT-07 (medium bug), framed as the ORM-relationship consistency convention. See [DAT-07](#dat-07) for the erasure/test-coverage angle.

**Locations:** `backend/app/models/user.py:63` (`User`); plus `backend/app/models/application_artifact.py:81`, `backend/app/models/promo_redemption.py:697`, `backend/app/models/promo_validation_attempt.py:722`. Prior audit: RELATED-TO WS1.

**Evidence.** `User` declares `delete-orphan` relationships for 13-14 owned tables, but none for `application_artifact`, `promo_redemption`, or `promo_validation_attempt` (all FK to `user.id` with `ondelete=CASCADE`). `delete_user_account` purges them only via the DB FK.

**Failure scenario.** On any backend not enforcing FKs (the SQLite dev/test path), deleting a user leaves these PII/audit rows orphaned; it also blocks ORM-level erasure verification for those tables.

**Suggested fix.** Add matching `relationship(cascade='all, delete-orphan')` on `User` for these tables, or explicitly document them as intentionally DB-only.

**Verification.** Confirmed 3/3 adversarial verifiers. `User` declares delete-orphan relationships for 14 tables but not the three named; test conftest sets no `PRAGMA foreign_keys=ON` so those rows orphan in the SQLite path — real, low (prod Postgres FK still cascades).

---

<a id="dat-13"></a>
### DAT-13 — delete_for_search re-queries then deletes rows one-by-one instead of bulk DELETE
⚪ **LOW** · ⚡ perf · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: XS · WS33

**Locations:** `backend/app/repositories/digest.py:32` (`delete_for_search`); plus `backend/app/services/digest.py:112`.

**Evidence.** `delete_for_search` calls `self.list_for_search` (a fresh SELECT with `joinedload` of `seen_job`) and then issues one `session.delete(row)` per pending row. So flushing a digest of N jobs runs 1 SELECT + N DELETEs where a single `delete().where(search_id == ...)` would suffice. `flush_due` has already loaded `pending` via `list_for_search`, so the eager-loaded SELECT is also redundant.

**Failure scenario.** A large digest (many queued jobs) emits N individual DELETE statements plus a redundant eager-loaded SELECT on every `flush_due` tick, inflating DB round-trips proportional to digest size.

**Suggested fix.** Replace with a single bulk `session.execute(delete(PendingDigest).where(PendingDigest.search_id == search_id))`.

**Verification.** Confirmed 3/3 adversarial verifiers. `flush_due` loads `pending` via `list_for_search` (line 61), then `delete_for_search` re-runs the same joinedload SELECT and does one `session.delete` per row; the redundant eager SELECT + N deletes are real, correctly low perf.

---

<a id="dat-14"></a>
### DAT-14 — Ghost-detection sweep full-scans seen_job (no index on status/applied_at)
⚪ **LOW** · ⚡ perf · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: S · WS33

> Same missing-index root cause as DAT-03 (medium) and DAT-11 (low); kept distinct because it isolates the scheduled ghost-detection predicate.

**Locations:** `backend/app/repositories/ghost_detection.py:483` (`GhostDetectionRepository.list_stale_applications`). Note: the cited line 483 is stale; the query is near line 18. Plus `backend/app/models/seen_job.py:24`.

**Evidence.** The scheduled query filters `status == 'applied' AND applied_at <= cutoff AND ghosted_at IS NULL` across all searches. `seen_job` has only `ix_seen_job_search_id` — no index on `status` or `applied_at`.

**Failure scenario.** As `seen_job` grows into the system's largest table, each ghost-detection tick full-scans it, adding periodic DB load that scales with total job history.

**Suggested fix.** Add a composite/partial index matching the sweep predicate, e.g. `(status, applied_at)` or a partial index `WHERE ghosted_at IS NULL`.

**Verification.** Confirmed 3/3 adversarial verifiers. `list_stale_applications` filters `seen_job` on `status`/`applied_at`/`ghosted_at` unscoped across all searches; `seen_job` has only `ix_seen_job_search_id`, so the periodic sweep full-scans — cited line 483 is really ~18 but the defect holds.

---

<a id="dat-15"></a>
### DAT-15 — InboxPollState upsert is non-atomic get-then-insert; concurrent first poll violates unique
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: low (3/3 verifiers) · Effort: S · WS33

**Locations:** `backend/app/repositories/inbox_poll_state.py:20` (`InboxPollStateRepository.upsert_last_polled_uid`); plus `backend/app/models/inbox_poll_state.py:18`, `backend/app/services/inbox_orchestration.py:146`.

**Evidence.** `upsert_last_polled_uid` reads `get_for_user` then INSERTs when it returns `None`, with no lock. `inbox_poll_state.user_id` is UNIQUE. A redelivered `process_inbox_messages` overlapping the next tick for a first-time user (no existing row) can have both passes insert, causing an `IntegrityError` on the second.

**Failure scenario.** The first-ever poll for a user runs on two overlapping passes; both insert a poll-state row, the unique constraint aborts one pass, and its cursor advance is lost.

**Suggested fix.** Use `INSERT ... ON CONFLICT (user_id) DO UPDATE`, or wrap the insert in a savepoint and fall back to update on `IntegrityError`.

**Verification.** Confirmed 3/3 adversarial verifiers. `inbox_poll_state.user_id` is `unique=True`; upsert does a non-atomic get-then-insert with no `ON CONFLICT`/savepoint. Two overlapping `acks_late` ticks for a first-time user can both INSERT and violate the constraint — real low-confidence race.

---

<a id="dat-16"></a>
### DAT-16 — sync_after_scrape materializes every SeenJob row for a search each scrape to diff status
⚪ **LOW** · ⚡ perf · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: M · WS33

> Merged with DAT-17 (uid 41, `jobs.py:860`, same symbol, confirmed 3/3) — identical defect. Combined here as one finding.

**Locations:** `backend/app/repositories/jobs.py:862` (`SeenJobRepository.sync_after_scrape`). Note: the real code is around line 81-83; the cited lines (860/862) are stale but the symbol resolves. Called every scrape at `backend/app/services/pipeline.py:99`.

**Evidence.** `rows = list(self.session.scalars(select(SeenJob).where(SeenJob.search_id == search_id)))` loads the entire dedup history for the search on every scrape tick, then loops in Python to flip `closed`/`seen` status based on membership in `scraped_external_ids`. There is no upstream cap on ledger size.

**Failure scenario.** A long-lived search accumulating tens of thousands of seen jobs re-fetches the full row set into the worker on every scheduler tick to close/reopen postings, growing memory and tick time linearly with history rather than with the small delta that actually changed.

**Suggested fix.** Do the close/reopen as two targeted set-based `UPDATE ... WHERE` statements keyed on the scraped external_ids, instead of loading and iterating every historical row.

**Verification.** Confirmed 3/3 adversarial verifiers (merged record DAT-17 also 3/3). `sync_after_scrape` (jobs.py:81-83, not the cited 860/862) does `list(session.scalars(select(SeenJob).where(search_id == ...)))` and loops in Python each scrape; `pipeline.py:99` calls it every tick with no upstream cap — real but low perf finding.

---

<a id="dat-18"></a>
### DAT-18 — Reset/verify token single-use relies only on post-use deletion, no consumed marker
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: S · WS18

**Locations:** `backend/app/repositories/password_reset_tokens.py:22` (`get_valid_by_hash`); plus `backend/app/repositories/email_verification_tokens.py:22`, `backend/app/services/auth.py:132`.

**Evidence.** `get_valid_by_hash` only filters on `expires_at > now`. Single-use is enforced solely by `delete_for_user()` after a successful reset — there is no `used_at` column. If the closing delete is skipped, or the transaction partially fails/rolls back while keeping the row, the raw token remains replayable until expiry.

**Failure scenario.** Any code path or future refactor that validates a token but doesn't reach `delete_for_user` (or a rollback that keeps the row) leaves a still-valid reset link reusable within the 60-minute window.

**Suggested fix.** Mark tokens consumed atomically (a `used_at` column, or delete in the same statement that reads them) so validity never depends on a later best-effort delete.

**Verification.** Confirmed 3/3 adversarial verifiers. `get_valid_by_hash` filters only `expires_at > now`; single-use is enforced by `delete_for_user` after use with no `used_at` column. Largely mitigated by the same-transaction atomicity of the update+delete, so valid only as low defense-in-depth as rated.
