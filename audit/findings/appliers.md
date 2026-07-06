# Appliers — auto-apply adapters (ATS integrations)

This area covers `backend/app/appliers/` — the pluggable adapters that autonomously submit real job applications to ATS platforms (Workday, Greenhouse, Lever, Ashby, SmartRecruiters, LinkedIn, Indeed, Microsoft/SmartApply, Apple, Meta, Uber, Google, Amazon) plus their shared payload/resume/questionnaire helpers. The headline finding is a systemic **false-success** class: several live-submit paths (Apple, Microsoft, Meta multipart, Workday name/terms, Indeed/LinkedIn) accept an HTTP 200 that carries an error/`success:false` body and report `status=submitted` for an application that never went through — the exact WS4 Greenhouse fix left un-swept across sibling adapters. Alongside it are data-integrity defects (parallel-array desync, over-eager fuzzy WID matching, silently-dropped required answers, a stringified resume-meta dict), a live Indeed submit that drops the session cookies it gates on, and a cluster of credential-hygiene and safe-default gaps.

**Summary:** critical 0 · high 4 · medium 10 · low 13 (27 confirmed findings; several near-duplicates merged below, so 21 rendered).

---

<a id="apl-01"></a>
### APL-01 — Apple applyJob reports submitted on {"success": false} 200 body despite modeling it
🟠 **HIGH** · 🐞 bug · Status: ✅ done (2026-07-03, fixed `a294e81`) · Confidence: high (5/5 verifiers) · Effort: S · WS23

**Update (2026-07-03).** Fixed: `apply()` now calls `apply_error_message(response)` after `submit_apply_job` and returns `status=failed` on a `{"success": false}` body (regression-tested by `test_live_submit_fails_on_success_false_body`). A narrower residual — a 200 body with bare `errors` and no `success` key — is tracked as [APL-28](#apl-28).

**Locations:** `backend/app/appliers/adapters/apple_careers_live.py:121` (`submit_apply_job`); plus `backend/app/appliers/adapters/apple_careers.py:165`, `backend/app/appliers/adapters/apple_careers_common.py:147`.

**Evidence.** `submit_apply_job` returns `http.put_json(...)` directly, and `apply()` then returns `status=submitted` with `extract_application_id(response)`. The codebase already models the failure envelope: `unwrap_response` explicitly branches on `response.get('success') is True`. So the API can return `{"success": false}` at HTTP 200, yet the submit path never checks that flag.

**Failure scenario.** Apple returns `200 {"success": false, ...}` (e.g. a missing questionnaire answer or a closed req). `extract_application_id` yields `None`, but the status is still `submitted`, so the user and the pipeline believe the application went through when it did not.

**Suggested fix.** After `put_json`, treat `success != True` (or the presence of `errors`) as a failure and return `status=failed` with the message, matching the `{success}` convention `unwrap_response` already relies on.

**Verification.** Confirmed 5/5 adversarial verifiers. `submit_apply_job` returns `put_json` raw, `apply()` (l165-180) marks submitted; `unwrap_response` explicitly branches on `success is True`, proving a `{success:false}` 200 is modeled yet unchecked on submit.

<a id="apl-02"></a>
### APL-02 — Indeed live Easy Apply submit never sends the session cookies it gates on
🟠 **HIGH** · 🐞 bug · Status: ✅ done (2026-07-03, fixed `b306290`) · Confidence: high (5/5 verifiers) · Effort: S · WS23

**Update (2026-07-03).** Fixed: `_credential_headers` now serializes `credentials["cookies"]` into a `Cookie` header that reaches the smartapply submit (a test asserts the cookies on the wire). The manual string-join serialization (vs httpx `cookies=`) is a hardening residual tracked as [APL-29](#apl-29).

**Locations:** `backend/app/appliers/adapters/indeed.py:124` (`IndeedApplier._apply_hosted`).

**Evidence.** After passing `has_indeed_session_cookies(ctx.credentials)`, the live POST is `self.http.post_json(SMARTAPPLY_SUBMIT_URL, json=body, headers=headers)` — with no `cookies=`. `_credential_headers` forwards only `credentials['headers']` plus CSRF, never a `Cookie` header. The sibling LinkedIn adapter (`linkedin.py:211`) correctly threads `cookies=cookies`.

**Failure scenario.** A user stores valid Indeed PPID/SOCK cookies and enables auto-apply; the live submit hits smartapply anonymously (the default `HttpClient` has no cookies) and Indeed rejects it — every Indeed-hosted apply silently fails.

**Suggested fix.** Thread the credential cookies into the smartapply POST (e.g. `cookies=credentials['cookies']`), mirroring LinkedIn's `voyager_request_cookies` usage.

**Verification.** Confirmed 5/5 adversarial verifiers. `apply.py:136` uses `get_applier` with no http so `self.http` is cookieless; `_apply_hosted` POST (l124) has no `cookies=` and `_credential_headers` never builds a Cookie header, yet `has_indeed_session_cookies` gates on `credentials['cookies']`; LinkedIn threads cookies, Indeed drops them.

<a id="apl-03"></a>
### APL-03 — Microsoft/Apple SmartApply submits report success on 200 error body (no post-2xx check)
🟠 **HIGH** · 🐞 bug · Status: 🔜 in progress (2026-07-03, `a294e81`) · Confidence: high (5/5 verifiers) · Effort: S · WS23

**Update (2026-07-03).** Partially fixed: Microsoft `apply()` now checks `api_error_message()` after candidate/resume/submit — the Microsoft path is fully closed (a claim that top-level string `error` bodies slip through was refuted; the real envelope models `error` as a dict, which is caught). Apple's `apply_error_message` is stricter and still misses bare-`errors` bodies, so the Apple half remains open as [APL-28](#apl-28).

Merged with APL-07 (same defect, one location list): Microsoft SmartApply and Apple `applyJob` both ignore a `success:false`/`errors` body after a 2xx.

**Locations:** `backend/app/appliers/adapters/microsoft_careers.py:143` (`MicrosoftCareersApplier.apply`); plus `microsoft_careers.py:131`, `:136`, `:180`, and `apple_careers.py:165`, `apple_careers_live.py:121`, `apple_careers_common.py:147`.

**Evidence.** `response = http.post_json(submit_url(...), json=submit_body)` is followed straight by `app_id = extract_application_id(response)` with no check for `{"errors":[...]}` / `{"success":false}`; `post_json`/`put_json` only `raise_for_status` on non-2xx. Apple's `submit_apply_job` returns `put_json` raw and `unwrap_response` has a `success is True` branch but never raises on `success:false`. Sibling adapters (Amazon `api_error_message`, Uber/Meta/Google error envelopes) all inspect the body.

**Failure scenario.** SmartApply or Apple returns HTTP 200 with an error/validation body (missing required answer, expired session, duplicate application). `extract_application_id` returns `None`; the adapter returns `status=submitted`, so the pipeline marks the job applied though it never was.

**Suggested fix.** Add an `api_error_message`-style body check (like `amazon_jobs_common`) after each MS POST (submit, `_save_candidate`, `upload_resume`) and after Apple `applyJob`; fail on `success:false`/`error`/`errors`, mirroring the WS4 Greenhouse fix.

**Verification.** Confirmed 5/5 adversarial verifiers (APL-03), 3/3 on the merged APL-07. `raise_for_status` only catches non-2xx; MS submit (l143-156) goes straight to `extract_application_id`, and Apple `unwrap_response` only branches on `success is True`, never raising on `success:false`, unlike Amazon (`api_error_message` l132/164), Uber and Google.

<a id="apl-04"></a>
### APL-04 — Required questionnaire answer silently dropped when value present but unresolvable
🟠 **HIGH** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/5)) · Confidence: high (5/5 verifiers) · Effort: S · WS24

**Update (2026-07-09).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/5): when a required question has a present `raw_value` but `_answer_entry` returns `None`, the question id is appended to `missing_required` (optional questions still drop silently).

**Update (2026-07-03).** Re-verified still open — the fix wave never touched `workday_questionnaire_answers.py`. Reproduced: `build_questionnaire_answers({required numeric q}, {"q-num": "0"}) → ([], [])` (should flag `q-num` as missing).

Merged with APL-10 (same defect at the same guard, `build_questionnaire_answers` line 48): a present-but-unconvertible required answer — unmatched choice label, numeric `'0'`/non-int — is dropped without being flagged.

**Locations:** `backend/app/appliers/adapters/workday_questionnaire_answers.py:48` (`build_questionnaire_answers`); plus `workday_questionnaire_answers.py:95` (`_resolve_choice_ids`).

**Evidence.** The required guard fires only `if raw_value is None`, treating any present value as answered. For choice types `_answer_entry` -> `_resolve_choice_ids` returns `None` when no WID/label matches (l96-99), and for numeric types a non-int/`'0'` value likewise yields no entry; the entry is dropped yet the `question_id` is never added to `missing_required`. Test `:73` asserts `missing == []` for a dropped numeric answer.

**Failure scenario.** A profile answer for a required single-choice question doesn't exactly match any option label (or a required numeric question holds `'0'`/`'N/A'`) -> the entry is dropped, `missing_required` stays empty, and the questionnaire is POSTed without the required answer after the application has already been created — an incomplete application or an opaque Workday rejection.

**Suggested fix.** When the question is required and a non-`None` `raw_value` yields no entry from `_answer_entry`/`_resolve_choice_ids` (or a choice resolves to zero ids), append `question_id` to `missing_required` instead of dropping it.

**Verification.** Confirmed 5/5 adversarial verifiers (APL-04), 3/3 on the merged APL-10. Unresolvable required choice yields `entry=None` (l55) and is never added to `missing_required` (l50 branch skipped), so submit POSTs without it (`workday_questionnaire.py:178`). One verifier argued for medium (recoverable incomplete apply); kept high per the record's severity.

---

<a id="apl-05"></a>
### APL-05 — Meta resume (multipart) submit skips the GraphQL errors check the JSON path enforces
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/39)) · Confidence: high (3/3 verifiers) · Effort: S · WS23

**Locations:** `backend/app/appliers/adapters/meta_careers_graphql.py:92` (`post_graphql_multipart`); plus `meta_careers_graphql.py:112`, `meta_careers_live.py:51`.

**Evidence.** `post_multipart` returns a parsed dict for JSON responses; `post_graphql_multipart` then does `if isinstance(response, dict): return response`, bypassing `_parse_graphql_json`, which raises on `data['errors']`. The non-resume path (`post_graphql`) does check, and the applier only maps errors to `failed` via that `ValueError`.

**Failure scenario.** A Meta application *with* a resume attachment gets a `200 {"errors":[{"message":...}]}` rejection; because the multipart path returns it as-is, `submit_application` succeeds and the adapter reports `status=submitted` for a rejected application.

**Suggested fix.** Route the multipart dict response through `_parse_graphql_json` (or an equivalent errors-check) before returning, so resume submits fail on the same GraphQL error envelope as non-resume submits.

**Verification.** Confirmed 3/3 adversarial verifiers. `post_multipart` returns `resp.json()` dict; `post_graphql_multipart` returns it directly (l92-93) bypassing the `_parse_graphql_json` errors check, so a 200 `{'errors':[...]}` resume submit is reported submitted.

<a id="apl-06"></a>
### APL-06 — Meta education parallel arrays desync via per-column filters
🟡 **MEDIUM** · 🐞 bug · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: S · WS24

**Locations:** `backend/app/appliers/adapters/meta_careers_payload.py:53` (`build_application_state`); plus `meta_careers_payload.py:54`, `:55`, and test `backend/tests/appliers/test_meta_careers.py:57`.

**Evidence.** `collegeSchoolNames = [e.school for e in education if e.school.strip()]`, `collegeDegreeNames = [... if e.degree.strip()]`, and `collegeConcentration1Names = [... if e.field_of_study.strip()]` apply three *different* per-column filters over the same `education` list. This is the same class of work-history desync WS4 fixed, left unfixed for education.

**Failure scenario.** Education row A (school, no degree) plus row B (school + degree): `schools=[A,B]`, `degrees=[B]` -> Meta positionally attaches B's degree to A's school. Wrong education is submitted on a live apply.

**Suggested fix.** Filter education once into a single applicable-rows list (as work history was) and build every `college*` column from that same list.

**Verification.** Confirmed 5/5 adversarial verifiers. l53-55 use three independent per-column `.strip()` filters; `EducationEntry` fields all default to `''` independently, so a school-only row desyncs the positional arrays — the exact WS4 work-history class left unfixed for education.

<a id="apl-08"></a>
### APL-08 — Workday lookup prefix/substring fallback silently submits wrong degree/field/skill WID
🟡 **MEDIUM** · 🐞 bug · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: S · WS24

Merged with APL-09 (same `match_lookup_item` over-eager fallback; APL-09 anchored line 61, APL-08 line 70 — same two fallback branches). Highest-confidence record kept as the primary.

**Locations:** `backend/app/appliers/adapters/workday_lookup.py:61` and `:70` (`match_lookup_item`); plus `workday_education_lookup.py:77`, `workday_skill_lookup.py:60`.

**Evidence.** After the exact and normalized checks, `match_lookup_item` falls to prefix (`descriptor.startswith(target) or target.startswith(descriptor)`, l61-68) and then raw substring (`target in descriptor or descriptor in target`, l70-73), with no minimum-length or single-candidate guard. A short or common value like `'BS'`, `'Arts'`, `'Java'` substring-matches an unrelated row (e.g. `'Master of Arts'`, `'JavaScript'`). Test l97-104 shows `'Bachelor of Science'` matching row `'Bachelor of Science in Engineering'`. `workday_reference` then binds that WID for a live submit.

**Failure scenario.** A live Workday apply resolves degree `'Bachelor of Science'` to the WID for `'Bachelor of Science in Engineering'` (or skill `'Java'` -> `'JavaScript'`); a false credential is submitted to the employer with no user signal.

**Suggested fix.** Restrict auto-accept to exact/normalized-equal matches; for prefix/substring hits, gate on a minimum length and/or a single unambiguous candidate, otherwise fall back to the descriptor (self-reported text) or flag for review rather than binding a mismatched catalog id.

**Verification.** Confirmed 5/5 adversarial verifiers (APL-08), 3/3 on the merged APL-09. `match_lookup_item` prefix (l61-68) + substring (l70-73) fallbacks auto-bind a mismatched WID; `workday_reference` returns `match['id']` on live submit. Verifiers noted this is incorrect-but-recoverable and catalog-dependent, hence medium not high.

<a id="apl-11"></a>
### APL-11 — Workday name POST and terms PUT skip the post-2xx errorCode check sibling steps enforce
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: S · WS23

Merged with APL-12 (the `/name`-step subset of this same defect at `workday_submit.py:85`).

**Locations:** `backend/app/appliers/adapters/workday_submit.py:84` (`submit_live_application`); plus `workday_submit.py:148`, `workday_questionnaire.py:242`.

**Evidence.** The `/name` POST result is discarded (l85-89) and `submit_terms_consent`'s `put_json` body is ignored (l148). Every other section (skills/languages/experience/education via `_response_error`, finalize l172) checks `errorCode` in the 2xx body. A 200-with-`errorCode` name/terms rejection is swallowed and the flow proceeds to finalize. `test_workday_submit_flow.py:83` returns `{ok:True}` for `/name` and it is accepted.

**Failure scenario.** Workday returns 200 with `errorCode` for the name step (bad legal name) or the terms step (consent not recorded); the applier ignores it and finalizes, so the application is submitted with a missing name or without accepted terms while looking successful.

**Suggested fix.** Apply the same `errorCode`-on-2xx check used by the section submitters to the name POST response and the terms-consent PUT response; fail the submit (return `progress.failure(...)` with the application id) on error.

**Verification.** Confirmed 3/3 adversarial verifiers (APL-11), 3/3 on the merged APL-12. Name POST result (l85) and terms `put_json` body (l148) are discarded while sibling sections and finalize check `errorCode` on the 2xx body; a 200-with-`errorCode` name/consent rejection is swallowed and the flow finalizes.

<a id="apl-13"></a>
### APL-13 — flatten_lever_form_fields emits resume_file meta as dict-repr on live Lever submit
🟡 **MEDIUM** · 🐞 bug · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: S · WS24

Merged with APL-14 (identical defect and location, `resume.py:59`).

**Locations:** `backend/app/appliers/resume.py:59` (`flatten_lever_form_fields`); plus `lever.py:90`, `lever.py:218`.

**Evidence.** `flatten_lever_form_fields` only special-cases `'urls'`/`'consent'`/`bool`; every other key falls to `else: parts[key] = str(value)`. On the resume-present multipart branch (l87-92) the payload always carries `resume_file = resume_meta_for_payload()` — a dict (`{'filename':..., 'content_type':..., 'size_bytes':...}`, l218-220) — which is then flattened, so the form gets `resume_file="{'filename': ...}"` (a stringified Python dict) beside the real file part.

**Failure scenario.** A user live auto-applies to a Lever posting with a resume -> Lever receives a bogus `resume_file` form field holding a Python dict repr *plus* the real file part; a malformed submit that Lever may reject on field validation or store as garbage.

**Suggested fix.** Drop the metadata-only `resume_file` key from the payload before flattening (the file is sent as a part), or make `flatten_lever_form_fields` skip/`json.dumps` dict values it cannot map.

**Verification.** Confirmed 5/5 adversarial verifiers (APL-13), 3/3 on the merged APL-14. On the resume-present multipart branch, `payload['resume_file']` is the `model_dump()` dict (l218-220) and `flatten_lever_form_fields` `str()`s it into a dict-repr form field beside the file part — confirmed malformed live submit.

---

<a id="apl-15"></a>
### APL-15 — Apple questionnaireAnswers dumps profile.answers verbatim, not mapped to question ids
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: M · WS24

**Locations:** `backend/app/appliers/adapters/apple_careers_live.py:54` (`questionnaire_answers`).

**Evidence.** `mapped = {key: value for key, value in profile_answers.items() if value}`; the answers are sent under the fetched questionnaire id without checking that questionnaire's actual question ids/options. This is the verbatim-answers class WS4 fixed for Microsoft (`build_answers` is now driven by the fetched questions).

**Failure scenario.** A profile has EEO or other answer keys unrelated to this req's questions; Apple's `applyJob` receives arbitrary keys under `answers`, which the questionnaire endpoint may reject or ignore, sending wrong/unexpected data for a submitted application.

**Suggested fix.** Drive the answers map from the fetched questionnaire's question ids (like Microsoft `build_answers`) instead of dumping every profile answer key.

**Verification.** Confirmed 3/3 adversarial verifiers. `apple_careers_live.py:54` dumps all `profile_answers` keys verbatim under `questionnaireAnswers` with no mapping to fetched question ids, unlike Microsoft `build_answers` which is explicitly question-driven; sent in live apply.

<a id="apl-16"></a>
### APL-16 — Indeed & LinkedIn-hosted live submit skip the post-2xx error-body check siblings enforce
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: S · WS23

Merged with APL-18 (the record's own `verify_note` flags it as a duplicate of uid 122 — same defect at `indeed.py:132` and `linkedin.py:215`).

**Locations:** `backend/app/appliers/adapters/indeed.py:132` (`IndeedApplier._apply_hosted`); plus `backend/app/appliers/adapters/linkedin.py:215` (`LinkedInApplier._apply_hosted`).

**Evidence.** After `post_json`, both adapters go straight to `_extract_application_id` and return `status='submitted'`. Ashby (`success is False`), Greenhouse (`_response_has_error`, added by WS4 at l100), Lever (`ok is False`) and SmartRecruiters (message without `applicationId`) all inspect the 2xx body first; Indeed and LinkedIn do not.

**Failure scenario.** smartapply/Voyager returns a 200 with an error body (validation failure, rate-limit soft-block, duplicate application, unmapped required question); the adapter reports `submitted` with no id, so the pipeline marks the job applied though nothing was submitted.

**Suggested fix.** Add the sibling error-body guard (`success:false` / `error` / `errors` / message-without-id) before extracting the application id on both hosted submit paths.

**Verification.** Confirmed 5/5 adversarial verifiers (APL-16), 5/5 on the merged APL-18. `indeed.py:132` and `linkedin.py:215` skip the sibling 2xx error-body guard present in Greenhouse (`_response_has_error:100`) and Ashby (`success is False:94`); a 200 error body is mis-recorded as submitted. Distinct from APL-02 (which is about dropped cookies on the Indeed submit).

<a id="apl-17"></a>
### APL-17 — LinkedIn/Indeed live apply hits private APIs with user cookies; no ToS/ban warning
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: M · WS25

**Locations:** `backend/app/appliers/adapters/linkedin.py:211` (`LinkedInApplier._apply_hosted`); plus `linkedin_voyager.py:84`, `linkedin_resume_upload.py:25`, `indeed.py:124`, `indeed_easy_apply.py:12`.

**Evidence.** `linkedin.py` POSTs to `/voyager/api/...` and Ambry; `indeed.py` POSTs `smartapply.indeed.com/beta/...` — both internal/private APIs driven by the candidate's own `li_at`/`JSESSIONID` or PPID/SOCK cookies. The docs have opt-in gating but no ToS/account-ban warning.

**Failure scenario.** A user enables `auto_apply` with real LinkedIn/Indeed cookies; automated Voyager/smartapply traffic trips anti-automation defenses and LinkedIn/Indeed suspends or bans their personal account.

**Suggested fix.** Add an explicit ToS/account-risk disclosure and consent before any live LinkedIn/Indeed cookie-driven submit; document the private-API/ban risk in the launch-checklist Safety section.

**Verification.** Confirmed 3/3 adversarial verifiers. `linkedin.py`/`indeed.py` drive private Voyager/smartapply APIs with the user's own `li_at`/`JSESSIONID` cookies and launch-checklist §7 has no ToS/ban warning. A verifier noted this is a doc/defense-in-depth disclosure gap, not a code exploit, so a higher rating would be inflated — low is fair.

<a id="apl-19"></a>
### APL-19 — LinkedIn resume upload forwards session cookies to a response-supplied URL
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: S · WS25

**Locations:** `backend/app/appliers/adapters/linkedin_resume_upload.py:37` (`upload_easy_apply_resume`).

**Evidence.** `upload_url = _first_string(value, 'singleUploadUrl', 'uploadUrl', 'url')` comes from the LinkedIn metadata JSON; then `http.put_raw(upload_url, content=..., cookies=cookies)` forwards the full session cookie jar. httpx sends the explicit `cookies=` to whatever host the URL resolves to. The existing SSRF guard blocks only private IPs, not foreign public hosts.

**Failure scenario.** If the metadata response is tampered with (MITM without cert pinning, or a LinkedIn-side redirect to a foreign host), the candidate's `li_at` session cookie is sent to an attacker-controlled origin, enabling account takeover.

**Suggested fix.** Upload to the signed Ambry URL *without* the session cookie jar (signed URLs self-authenticate), or assert the upload host is an expected licdn/linkedin domain before forwarding cookies.

**Verification.** Confirmed 3/3 adversarial verifiers. `upload_url` is taken from LinkedIn metadata JSON; `put_raw` forwards the full cookie jar (incl. `li_at`) via `voyager_request_cookies`. The SSRF guard blocks only private IPs, not foreign public hosts, so a MITM/redirect leaks the session cookie — a real hardening gap.

<a id="apl-20"></a>
### APL-20 — Microsoft CSRF fetch swallows all exceptions via bare except Exception
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: XS · WS23

**Locations:** `backend/app/appliers/adapters/microsoft_careers_common.py:90` (`resolve_csrf_token`).

**Evidence.** `try: html = http.get_text(apply_url) / except Exception: return None`. A blanket `Exception` catch hides non-HTTP failures (SSRF `assert_safe_outbound_url` `ValueError`, programming errors) and reduces them to a generic "requires CSRF token" error instead of surfacing the real cause. The sibling Apple `fetch_questionnaire` uses a narrow `except httpx.HTTPError`.

**Failure scenario.** `assert_safe_outbound_url` raises on a malformed `apply_url`, or an unexpected bug occurs; the user sees the misleading "requires a CSRF token" message and the real error is lost, hampering diagnosis.

**Suggested fix.** Narrow the `except` to `httpx.HTTPError` (the intended transient case) so unexpected errors propagate or are logged.

**Verification.** Confirmed 3/3 adversarial verifiers. `microsoft_careers_common.py:90` `except Exception` swallows `UnsafeOutboundUrlError`/programming errors from `get_text`, reducing them to a generic "requires CSRF" message; the sibling Apple fetch uses a narrow `except httpx.HTTPError`.

<a id="apl-21"></a>
### APL-21 — Uber dry-run payload embeds live session_token, persisted to ApplicationLog
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: XS · WS24

**Locations:** `backend/app/appliers/adapters/uber_careers_payload.py:110` (`build_application_payload`).

**Evidence.** `build_application_payload` passes `session_token` into `build_application_form_request`, which sets `"sessionToken": session_token or ""` in the preview `application_form_request`. `apply.py:215` persists `result.payload` for every attempt, including `dry_run`. Meta and Apple keep live tokens out of their preview payloads.

**Failure scenario.** A dry-run Uber apply writes the user's logged-in Uber Careers session token in cleartext into `application_logs.payload`, later returned via the application-log API.

**Suggested fix.** Build the preview `application_form_request` with `session_token=None` (redact `sessionToken`), matching Meta (`include_submit_input` gate) and Apple (placeholder talent id).

**Verification.** Confirmed 3/3 adversarial verifiers. `resolve_session_token` pulls the live token from credentials, embedded verbatim as `sessionToken` in the dry-run preview payload (`uber_careers.py:99`), persisted to `ApplicationLog.payload` for every attempt and exposed via the application-log schema; Meta/Apple redact.

<a id="apl-22"></a>
### APL-22 — request_headers lets stored credential headers overwrite CSRF/Content-Type/Referer
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: S · WS24

**Locations:** `backend/app/appliers/adapters/workday_common.py:145` (`request_headers`).

**Evidence.** After setting `Accept`, `Content-Type`, the CSRF token and the session id, `headers.update(cred_headers)` blindly merges arbitrary stored credential headers last, so a stale/mistyped CSRF, `Content-Type`, or `Cookie` in `credentials.headers` silently overrides the freshly-resolved values.

**Failure scenario.** A user stores a `headers` entry (an old `Content-Type` or a duplicate CSRF header) in site credentials; it clobbers the adapter's computed header and every live CXS POST is rejected or mis-signed.

**Suggested fix.** Merge credential headers first as a base, then apply computed headers, or whitelist which credential headers may be carried; never let them override CSRF/Content-Type.

**Verification.** Confirmed 3/3 adversarial verifiers. `workday_common.py:147` `headers.update(cred_headers)` runs after the computed CSRF/Content-Type/Referer, so stored credential headers override them; real, but a self-inflicted misconfig with recoverable own-user impact.

<a id="apl-23"></a>
### APL-23 — Multi-choice questionnaire answer silently submits only resolvable selections
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: S · WS24

Merged with APL-25 (same defect at `_resolve_choice_ids` line 126; APL-25's `verify_note` explicitly calls it a near-exact duplicate of this record).

**Locations:** `backend/app/appliers/adapters/workday_questionnaire_answers.py:126` (`_resolve_choice_ids`).

**Evidence.** For multi-choice, the comma-split values are resolved independently (l136-142); parts matching no `possibleAnswers` (not a WID, no exact `answerText` match, l146-152) are dropped with no signal. If at least one part matches, `_answer_entry` returns non-`None` (l97-99), so the partial set is submitted as complete. Only an all-miss (empty list) drops the entry. `missing_required` only fires when `raw_value is None`, so there is no upstream guard.

**Failure scenario.** A profile answer `'Python, Rust'` for a multi-select where `'Rust'` isn't an option submits only `'Python'` to a live Workday questionnaire; the applicant's stated selection is silently truncated.

**Suggested fix.** Track unresolved multi-choice tokens and surface them (flag for review, or add to `missing_required` when the question is required, or show in preview) instead of silently discarding them.

**Verification.** Confirmed 3/3 adversarial verifiers (APL-23); the merged APL-25 was 2/3 (one refuted, on duplicate grounds). `_resolve_choice_ids` resolves comma-split multi values independently, drops unmatched labels, and one match makes `_answer_entry` non-`None` so a partial set submits.

<a id="apl-24"></a>
### APL-24 — Any 32-hex value trusted as a valid answer/lookup id without membership check
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: S · WS24

**Locations:** `backend/app/appliers/adapters/workday_questionnaire_answers.py:137` (`_resolve_choice_ids`); plus `backend/app/appliers/adapters/workday_lookup.py:42`.

**Evidence.** `if _WORKDAY_ID_RE.match(value): resolved.append(value)` accepts any 32-hex string as a choice id without checking `possibleAnswers`. The same holds in `workday_lookup.workday_reference` (l83-84) / `match_lookup_item` (l42-46): a WID not in the catalog is returned as `{id: <wid>}` verbatim. Test l162-172 proves an out-of-catalog WID is accepted.

**Failure scenario.** A stale/wrong WID in `profile.answers` or config is submitted as the answer id for the wrong question -> Workday accepts an id belonging to a different question, or rejects after the app has been created.

**Suggested fix.** Validate a supplied WID against the question's `possibleAnswers` (choice) / fetched candidates (lookup) before accepting; otherwise fall back to a label match or the descriptor.

**Verification.** Confirmed 3/3 adversarial verifiers. l137-138 appends any 32-hex value without checking `possibleAnswers`; `workday_reference` l83-84 / `match_lookup_item` l46 return `{id:<wid>}` verbatim for a WID not in the catalog. Low: needs a stale raw WID, and is recoverable.

<a id="apl-26"></a>
### APL-26 — Live submit failure mid-flow leaves a partial, unfinalized application on the ATS
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: M · WS23

**Locations:** `backend/app/appliers/adapters/workday_submit.py:118` (`submit_live_application`).

**Evidence.** The flow creates the application, posts name, uploads resume, then submits experience/education/skills/languages/questionnaires and finalize. Any post-create step returns a failed `ApplyResult` but performs no cleanup/withdraw; a grep confirms no delete/withdraw call exists anywhere in the Workday cluster.

**Failure scenario.** A section POST fails (e.g. `VALIDATION_FAILED` on a skill); the user sees `failed` but a half-populated candidate application already exists on the employer's Workday tenant with no automatic withdrawal.

**Suggested fix.** Document the non-atomic flow and/or attempt a best-effort withdraw/delete on mid-flow failure; at minimum persist the `external_application_id` so the user can clean up.

**Verification.** Confirmed 3/3 adversarial verifiers. Grep confirms no withdraw/delete/rollback anywhere in the Workday cluster; each post-create step returns failed with no cleanup, leaving a partial application. `external_application_id` is persisted as a partial mitigation.

<a id="apl-27"></a>
### APL-27 — ApplyContext.dry_run defaults to False (live submit by default)
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: S · WS24

**Locations:** `backend/app/appliers/types.py:22` (`ApplyContext.dry_run`).

**Evidence.** `dry_run: bool = False` on the context that drives autonomous auto-apply; adapters treat a missing/false flag as a real submission. A safe-by-default for an irreversible action would be dry-run, with LIVE as an explicit opt-in.

**Failure scenario.** A future caller constructing `ApplyContext` without setting `dry_run` (a new worker/task, a refactor, a test) silently issues a real application to a recruiter on the user's behalf.

**Suggested fix.** Default `dry_run` to `True` and require callers to pass `dry_run=False` explicitly for live submits, matching the opt-in-for-LIVE intent.

**Verification.** Confirmed 3/3 adversarial verifiers. `dry_run` defaults to `False` on the auto-apply context; all current callers (`apply.py:134`, linkedin/indeed/shopify/snowflake) pass it explicitly so there is no live impact today, but the unsafe default is a legitimate safe-default finding.

---

<a id="apl-28"></a>
### APL-28 — Apple apply_error_message only rejects strict `success is False`; bare-`errors` 200 bodies still report submitted
🟡 **MEDIUM** · 🐞 bug · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: S · WS42

Residual of the APL-01/APL-03 fix (commit `a294e81`): the Apple and Microsoft error-body checks added in the same commit are asymmetric.

**Locations:** `backend/app/appliers/adapters/apple_careers_common.py:158` (`apply_error_message`).

**Evidence.** `apply_error_message` guards `if not isinstance(response, dict) or response.get("success") is not False: return None`, so it fires only on the canonical `{"success": false}` envelope. The sibling `api_error_message` (`microsoft_careers_common.py:166-178`), added in the same fix, has a fallthrough that inspects a bare `errors` list / `error` dict even when `success` is absent; Apple has no such fallthrough. `put_json` only `raise_for_status`es on non-2xx, so a 200 error body flows straight in.

**Failure scenario.** Apple `applyJob` returns `200 {"errors": [{"message": "missing required answer"}]}` (or `{"error": "…"}`) with no top-level `success`. `apply_error_message` returns `None`, `extract_application_id` returns `None`, and `AppleCareersApplier.apply` (`apple_careers.py:181-185`) returns `status="submitted"` with a null application id — the exact false-success class APL-01/APL-03 set out to close, left un-swept on the Apple path (`services/apply.py` treats `submitted` as terminal, so nothing downstream blocks it).

**Suggested fix.** Give `apply_error_message` the same fallthrough as `api_error_message`: when the body carries a non-empty `errors` list or an `error` value, return a message regardless of `success`. Add a regression test for `{"errors": [{"message": …}]}` without a `success` key.

**Verification.** Confirmed 3/3 adversarial verifiers (delta audit, 2026-07-03), median medium. Reproduced directly: `apply_error_message({"errors":[{"message":"…"}]})` → `None` while the Microsoft sibling returns the message. Kept medium not high — the canonical `success:false` rejection IS now caught and tested, so exploitability hinges on Apple emitting an error body without `success:false` (plausible for the undocumented endpoint, but unproven by a captured fixture).

---

<a id="apl-29"></a>
### APL-29 — Indeed Cookie header built by manual join of unvalidated credential values (self header-injection)
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: high (delta audit) · Effort: S · WS42

Residual of the APL-02 fix: the cookies are now correctly sent, but via a raw header join rather than the safer `cookies=` path.

**Locations:** `backend/app/appliers/adapters/indeed.py:175` (`_credential_headers`).

**Evidence.** The APL-02 fix serializes cookies as `"; ".join(f"{key}={value}" for key, value in cookies.items())` into a raw `Cookie` header, instead of httpx's `cookies=` parameter that the sibling LinkedIn submit uses (`linkedin.py:211`). Cookie values come from `CredentialCreate.cookies`, typed `dict[str, str]` with no content validation (`schemas/credential.py:20`), and httpx passes a value containing CRLF through untouched (verified empirically).

**Failure scenario.** A user stores an Indeed cookie whose value contains CRLF or a semicolon; the live smartapply POST carries `Cookie: PPID=<value-with-\r\n>`, splicing an extra request header or forging additional cookie morsels into the user's own outbound request. Bounded to self-injection (own credential, fixed URL, multi-user isolation intact) — defense-in-depth, not a cross-tenant exploit.

**Suggested fix.** Pass `cookies=credentials["cookies"]` to `post_json` and let httpx build/validate the morsels, mirroring LinkedIn.

**Verification.** Confirmed (delta audit, 2026-07-03). Does not reopen APL-02 — the cookies are correctly sent to the submit request now (a test asserts them on the wire); this is the serialization-hardening residual.
