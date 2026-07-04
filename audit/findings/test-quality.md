# Test quality (anti-coverage-theater)

This area examines whether the repository's 100%-coverage gate reflects real behavioral verification or merely line execution. Despite both stacks enforcing `fail_under = 100`, the audit found seven confirmed instances of coverage theater: assertion-free "no-op" tests, tests that assert fabricated states the real API never produces, tests that force production-only branches then run them against SQLite (which silently discards the very semantics under test), and whole subsystems (Alembic migrations, FK cascades, LaTeX render→compile) that no test actually exercises. None rise above medium severity because each is a hardening/verification gap rather than a proven live defect, but collectively they show the coverage number overstates the safety net — several known bugs elsewhere in the audit stay green precisely because of these gaps.

**Summary:** 0 critical · 0 high · 1 medium · 6 low.

---

<a id="tst-01"></a>
### TST-01 — Test SQLite engines never set PRAGMA foreign_keys=ON; cascade/FK behavior unenforced
🟡 **MEDIUM** · 🧪 test · Status: ☐ open · Confidence: certain · Effort: S · WS33

**Locations:** `backend/tests/conftest.py:60` (`db_session / client`); plus `backend/tests/conftest.py:91`, `backend/app/core/db.py:11`, `backend/tests/repositories/test_owned_repositories.py:20`.

**Evidence.** Both `create_engine('sqlite...')` calls omit any connect listener issuing `PRAGMA foreign_keys=ON`, and a grep confirms the pragma appears nowhere in the test suite. SQLite defaults foreign keys OFF, so the 18 tables' `ondelete=CASCADE` / `SET NULL` clauses never fire during tests, and no test asserts cascade behavior at the DB level.

**Failure scenario.** A change that drops a `CASCADE` (e.g. the GDPR user-erasure path) or otherwise regresses FK integrity passes the 100% gate; on the real Postgres backend users are left with orphaned PII (`application_artifact`, `promo_redemption`) or deletion outright fails.

**Suggested fix.** Register a SQLite connect listener that issues `PRAGMA foreign_keys=ON` on both test engines, and add a user-deletion cascade regression test.

**Verification.** Confirmed 3/3 adversarial verifiers. Neither test engine issues `PRAGMA foreign_keys=ON`, so DB-level `ondelete` rules never fire in tests. `User` does carry ORM `cascade='all,delete-orphan'` on direct children, so no live erasure bug is proven — this is a hardening/coverage-theater gap, which is why it sits at medium rather than higher.

---

<a id="tst-02"></a>
### TST-02 — Indeed hosted-submit test asserts body but never that the session cookies are sent
⚪ **LOW** · 🧪 test · Status: ☐ open · Confidence: high · Effort: XS · WS23

**Locations:** `backend/tests/appliers/test_indeed.py:196` (`test_hosted_live_submit_posts_to_smartapply`).

**Evidence.** The test handler records `request.method` and `request.body` and asserts on them, but never checks `request.headers['cookie']` or the cookie jar. As a result the test passes even though `indeed.py:124` drops the credential cookies (the companion "live-submit-drops-session-cookies" finding).

**Failure scenario.** The missing-cookie regression is invisible to CI: this test stays green even after the auth cookies are stripped from the real SmartApply request, so a broken authenticated-submit path ships undetected.

**Suggested fix.** Assert that the SmartApply request carries the credential cookies (e.g. `request.headers['cookie']` contains PPID/SOCK) so the authenticated path is actually exercised.

**Verification.** Confirmed 5/5 adversarial verifiers. The test at `test_indeed.py:234-237` asserts only method/body; `_credential_headers` (`indeed.py:165`) genuinely never attaches the cookie jar, so the cookie-drop regression stays green — an accurate coverage-theater gap.

---

<a id="tst-03"></a>
### TST-03 — Alembic migration chain never executed by tests (create_all used), hiding PG-only bugs
⚪ **LOW** · 🧪 test · Status: ☐ open · Confidence: high · Effort: M · WS33

**Locations:** `backend/tests/conftest.py:61` (`db_session`); related `alembic/env.py`.

**Evidence.** conftest builds the schema via `Base.metadata.create_all(engine)` on SQLite, and a grep shows no test invokes `alembic upgrade`/`downgrade`. The migrations use Postgres-only constructs (`INSERT ... RETURNING`, `sa.true()`, `op.create_foreign_key` ALTER, `batch_alter_table`) that `create_all` bypasses entirely.

**Failure scenario.** A migration that is broken on Postgres (bad reversibility, wrong `server_default`, drift from the models, or an ALTER SQLite would reject) ships green because the CI schema is generated from ORM metadata, not from the migration files.

**Suggested fix.** Add a CI job that runs `alembic upgrade head` (plus a downgrade round-trip) against a real Postgres, alongside a metadata-vs-migrations diff check.

**Verification.** Confirmed 3/3 adversarial verifiers. conftest builds the schema via `Base.metadata.create_all` on SQLite; no test or CI (`.github/workflows/ci.yml`) runs `alembic upgrade head`, so Postgres-only migration constructs are never executed. Low severity because no current defect is proven.

---

<a id="tst-04"></a>
### TST-04 — Lock-branch tests monkeypatch _is_sqlite=False on SQLite, asserting nothing about locking
⚪ **LOW** · 🧪 test · Status: ☐ open · Confidence: high · Effort: M · WS33

**Locations:** `backend/tests/repositories/test_jobs_deliveries_searches.py:117` (`test_claim_due_takes_row_lock_branch_on_non_sqlite`); plus `backend/tests/repositories/test_jobs_deliveries_searches.py:127`.

**Evidence.** The test sets `repo._is_sqlite = lambda: False` to force the `with_for_update(skip_locked=True)` branch, then runs it against in-memory SQLite (which silently drops the locking clause) and only asserts that the row id is returned. The `get_for_update` test is identical.

**Failure scenario.** The real Postgres `SKIP LOCKED` semantics (a contended row → `None` / disjoint claim sets) that guard the WS2 double-enqueue fix are never actually exercised, so a regression that breaks locking passes green.

**Suggested fix.** Cover the locking contract against Postgres (an integration/CI service) or at least assert the compiled SQL contains `FOR UPDATE SKIP LOCKED`; SQLite cannot validate this behavior.

**Verification.** Confirmed 3/3 adversarial verifiers. The tests set `repo._is_sqlite=lambda:False` to enter the `with_for_update(skip_locked=True)` branch but run against SQLite, which drops the clause, asserting only the returned id; `SKIP LOCKED` contention is never exercised — genuine coverage-theater.

---

<a id="tst-05"></a>
### TST-05 — Stripe-webhook 'unknown user is noop' tests assert nothing, cannot catch a regression
⚪ **LOW** · 🧪 test · Status: ☐ open · Confidence: high · Effort: S · WS22

**Locations:** `backend/tests/services/test_billing_part2.py:161` (`test_on_subscription_updated_unknown_user_is_noop`); plus `backend/tests/services/test_billing_part2.py:169`, `:68`, `:102`.

**Evidence.** The test bodies simply call `BillingService(db)._on_subscription_updated({...ghost customer...})` with no assertion. `billing.py:202`/`:218` look up a user and take the `None`-path early return; the test verifies only that no exception is raised, not that no user row was mutated or plan changed.

**Failure scenario.** If a handler regressed to mutate the wrong user's billing on an unknown-customer event, or looked up the user incorrectly, these tests still pass green — the no-op contract is entirely unverified.

**Suggested fix.** Add a control user and assert its billing fields (customer/subscription/plan) are unchanged after the call, rather than merely asserting no exception.

**Verification.** Confirmed 5/5 adversarial verifiers. Tests at lines 68/102/161/169 call handlers with no assert; `billing.py:202`/`:218` early-return on a `None` user, so a wrong-user mutation regression would still pass — verified assertion-free no-op tests.

---

<a id="tst-06"></a>
### TST-06 — Resume tests mock every compile/render path; render→compile contract untested
⚪ **LOW** · 🧪 test · Status: ☐ open · Confidence: high · Effort: S · WS27

**Locations:** `backend/tests/services/test_resumes.py:86` (`test_generate_single_tex_path`); plus `backend/tests/resumes/test_template.py:15`.

**Evidence.** `compile_fn` / `bundle_compile_fn` are always injected as `lambda: FAKE_PDF` and `render_template_bundle` is patched, while `test_template` only asserts special-character escaping. No test ever renders the real default template with heuristic `\item` experience and asserts it is compilable, so the over-escape bug passes the 100% gate.

**Failure scenario.** The itemize-breaking regression (`template.py` over-escaping `\item`) ships green because no test renders `default_template_tex` with heuristic experience fields and asserts a valid PDF / surviving `\item`.

**Suggested fix.** Add a test that renders `default_template_tex` with heuristic fields and asserts a real `\item` survives (or an integration compile smoke test when a compiler is present).

**Verification.** Confirmed 3/3 adversarial verifiers. `heuristic_fields.experience` contains raw `\item \textbf{...}` which `render_resume_template` passes through `_escape_latex` (escaping backslash/braces), and no test feeds heuristic experience through the default template; the over-escape bug is real and untested — legitimate coverage-theater.

---

<a id="tst-07"></a>
### TST-07 — Test asserts 'submitted' apply-result behavior the API never produces (coverage-theater)
⚪ **LOW** · 🧪 test · Status: ☐ open · Confidence: high · Effort: S · WS41

**Locations:** `frontend/src/hooks/jobMutations.test.tsx:79` (`'a submitted result also invalidates the jobs cache'`).

**Evidence.** The test mocks `api.applyToJob.mockResolvedValueOnce({ status: 'submitted' })` and asserts `['jobs']` invalidation. The real endpoint (`jobs.py:120`) always returns `'queued'` for a live apply; `'submitted'` is unreachable from the frontend, so the test validates a fabricated status.

**Failure scenario.** It gives false confidence that a live apply refreshes jobs via the hook. If the real async flow or the dialog's post-poll invalidation regresses, this test stays green because it exercises an impossible status.

**Suggested fix.** Test the actual `'queued'` path and its post-poll invalidation instead of a synthetic `'submitted'` return; remove or rewrite the branch it covers.

**Verification.** Confirmed 5/5 adversarial verifiers. `jobs.py:120` always returns `status='queued'` for a live apply; the hook's `result.status==='submitted'` branch (`jobMutations.ts:46`) is unreachable from the endpoint, so the test fabricates an impossible status.

---

<a id="tst-08"></a>
### TST-08 — `src/test/**` gate exclusion + deletion of `mockApiSamples.test.ts` left the mock builders unasserted
⚪ **LOW** · 🧪 test · Status: ☐ open · Confidence: high (delta audit) · Effort: S · WS42

**Locations:** `frontend/src/test/mockApiSamples.ts` (builder functions).

**Evidence.** `mockApiSamples.ts` has real logic — builder functions (`newSourceRecord`, `updatedSourceRecord`, …) that merge caller overrides via `...(data as object)`. Commit `702808e` deleted `mockApiSamples.test.ts` (60 lines of `toMatchObject` assertions) and excluded all of `src/test/**` from coverage, so the builders still execute (page tests drive them) but their behavior is asserted nowhere.

**Failure scenario.** Someone breaks a builder's override-merge or a default id; no test asserts the output and it's excluded from coverage, so `make check` stays green while the fixtures many page tests rely on are silently corrupted.

**Suggested fix.** Keep a small builder-contract test, or don't exclude the builder module from coverage.

**Verification.** Confirmed (delta audit, 2026-07-03). Test-infrastructure, so a reasonable trade-off — flagged as a genuine reduction in meaningful assertions beyond what the docs describe.
