# AI adapters — summaries, cover letters, resumes/LaTeX

This area covers the AI-facing subsystems: the summarizer/cover-letter/reply-drafter LLM adapters, the resume-tailoring pipeline (prompt building, JSON parsing, LaTeX template rendering, and PDF compilation), and the profile/template upload paths that feed them. The headline: two confirmed high-severity correctness bugs make the default-template resume path unusable (the renderer LaTeX-escapes the very `\item`/`\textbf` markup the itemize environment requires), plus a cluster of untrusted-LaTeX compilation weaknesses (no `-no-shell-escape`, no `\input` content scan, inherited environment, no resource limits) and a recurring prompt-injection gap where scraped job fields reach LLM prompts without the WS9 guard applied elsewhere.

**Summary:** 0 critical · 2 high · 5 medium · 13 low (20 confirmed findings; the LaTeX-escape defect is reported four times and is merged into one entry below, and the shell-escape/`\write18` concern appears at three severities and is merged into one entry, so 16 rendered entries).

---

<a id="aia-01"></a>
### AIA-01 — render_resume_template escapes structured LaTeX markup, breaking every default-template and AI-curated resume

🟠 **HIGH** · 🐞 bug · Status: ✅ done (WS26) · Confidence: high (5/5 verifiers) · Effort: M · WS26

**Fix.** `render_resume_template` now partitions placeholders: the `experience` field (controlled `\item`/`\textbf` markup) is substituted verbatim via `_RAW_LATEX_KEYS`, while every free-text / PII scalar is still escaped. `fields.py` escapes the free-text parts of each heuristic experience item (header, description, resume-text fallback) so user special characters cannot break the compile now that the field bypasses renderer escaping. The `escape_latex` helper was made public for reuse across the package. Regression tests assert `\item` survives rendering of both a direct field and the full default template with heuristic fields. Bundle rendering delegates to the same renderer, so user-uploaded templates are fixed identically.

**Locations:** `backend/app/resumes/template.py:31` and `:34` (`render_resume_template`); plus `backend/app/resumes/fields.py:64`/`:78` (heuristic `\item \textbf{...}` emission), `backend/app/resumes/prompts.py:10`/`:14`/`:15`/`:84` (SYSTEM_PROMPT requesting the same markup), `backend/app/resumes/default_template.tex:16`/`:17` (`[[experience]]` wrapped in `\begin{itemize}...\end{itemize}`).

This entry merges four records reporting the same defect: **AIA-01** (uid 75, line 34), **AIA-02** (uid 134, line 31), **AIA-05** (uid 79, line 34), and **AIA-15** (uid 140, line 31, typed `consistency`). All four were independently confirmed 5/5 or 3/3.

**Evidence.** `render_resume_template` loops over every placeholder — all 13 keys including `experience`, `education`, and `summary` — and runs each through `_escape_latex`, which turns `\` into `\textbackslash{}` and `{`/`}` into `\{`/`\}`. But both the heuristic path (`fields.py` emits `\item \textbf{...}`) and the LLM path (SYSTEM_PROMPT instructs the model to emit `\item \textbf{...}`, and `parse_curated_json` stores it raw) produce controlled LaTeX in those fields. After escaping, `\item \textbf{Title}` becomes the literal string `\textbackslash{}item \textbackslash{}textbf\{Title\}`.

**Failure scenario.** Any user without a custom template generates a tailored resume. `default_template.tex` wraps `[[experience]]` inside `\begin{itemize}...\end{itemize}`, but the substituted content now contains zero real `\item`, so tectonic/pdflatex aborts with "Something's wrong--perhaps a missing \item", exits nonzero, and `generate()` raises a ValidationError — the feature never produces a PDF on the default path. In any variant where compilation does proceed, the Experience/Education sections render as literal escaped `\item \textbf{...}` text instead of formatted bullets, degrading every non-custom and every AI-provider resume.

**Suggested fix.** Escape only free-text / PII scalar fields (name, contact, email); treat `experience`/`education`/`summary`/`skills` as pre-formatted LaTeX markup fields (the LLM and heuristic already emit controlled LaTeX), or escape per-field text while structurally re-inserting the `\item`/`\textbf` scaffolding. Pick one contract and align the prompt, parser, and renderer to it.

**Verification.** Confirmed 5/5 adversarial verifiers (AIA-01/-02/-05 at 5/5; AIA-15 at 3/3). Verifiers noted this is a functional, recoverable rendering/compile bug with no security or data impact; two suggested medium over high, but it makes the primary default-template path unusable, so high is retained.

---

<a id="aia-02"></a>
### AIA-02 — (merged into AIA-01)

🟠 **HIGH** · 🐞 bug · Status: ✅ done (WS26) · Confidence: high (5/5 verifiers) · Effort: M · WS26

See [AIA-01](#aia-01) — this record (uid 134, `backend/app/resumes/template.py:31`) is the same LaTeX-escape defect and is documented in full above.

---

<a id="aia-03"></a>
### AIA-03 — User LaTeX template compiled without -no-shell-escape and without an openin/sandbox restriction

🟡 **MEDIUM** · 🔒 security · Status: ✅ done · Confidence: high (5/5 verifiers) · Effort: M · WS27

**Locations:** `backend/app/resumes/compile.py` (`_run_compiler_workspace` / `_compiler_env`); plus `backend/app/resumes/template_bundle.py`, `backend/app/services/resumes.py`, `backend/app/api/v1/profile.py`.

This entry merges the shell-escape / `\write18` concern reported at three severities against the same code path: **AIA-03** (uid 138, medium, high confidence), **AIA-04** (uid 240, medium, medium confidence), and **AIA-09** (uid 135, low, defense-in-depth framing). All confirmed.

**Update (2026-07-10).** Fixed (tracker alignment): `compile_latex_workspace` already prefers tectonic, and the pdflatex fallback passes `-no-shell-escape` under a minimal `_compiler_env()` that forces `openin_any=p` / `openout_any=p` / `shell_escape=f` (shipped in `0135f08`). Regression coverage now asserts the pdflatex argv flag and sandbox env (and that app secrets are not forwarded). Companion content-scan / absolute-`\input` layer closed as [AIA-06](#aia-06); upload-time deny-list depth (`\read`, home-path includes, zip validate parse) closed as [AIA-07](#aia-07).

**Evidence (pre-fix).** pdflatex was invoked with only `-interaction=nonstopmode` and `-output-directory`; there was no `-no-shell-escape`, and no `env=` forcing `openin_any=p`/`openout_any=p`. The compiled body is the user's uploaded template bundle — render only substitutes `[[placeholder]]` values, and the `.tex/.sty/.cls` bytes pass through verbatim. TeX Live defaults (`openin_any=a`, `shell_escape=p`) read arbitrary files and enable restricted `\write18`; a host configured with `shell_escape=t` enables unrestricted `\write18`.

**Failure scenario.** An authenticated user uploads a template containing `\immediate\write18{...}`; if the worker's TeX config enables shell-escape (host-dependent), this is arbitrary command execution in the compile process, running with the app's environment. Even without shell-escape, restricted `\write18` plus the unrestricted `openin_any` broadens the read/exec foothold. tectonic is tried first (sandboxed, no shell-escape by default), and pdflatex is only the fallback, which is why verifiers scoped this medium rather than high.

**Suggested fix.** Prefer/pin tectonic (sandboxed); for the pdflatex fallback pass `-no-shell-escape` and run under `env` with `openin_any=p`/`openout_any=p`/`shell_escape=f`, isolating the workdir. Do not rely on host `texmf.cnf` defaults.

**Verification.** Confirmed 5/5 (AIA-03), 3/3 (AIA-04), and 5/5 (AIA-09). Verifiers noted the trigger is operator-precondition-gated (host shell-escape config), no compiler is installed in the Dockerfile, and tectonic-first mitigates — medium/defense-in-depth is fair.

---

<a id="aia-04"></a>
### AIA-04 — (merged into AIA-03)

🟡 **MEDIUM** · 🔒 security · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: S · WS27

See [AIA-03](#aia-03) — this record (uid 240, `backend/app/resumes/compile.py:92`) is the same shell-escape concern and is documented in full above.

---

<a id="aia-06"></a>
### AIA-06 — Bundle .tex content passed to compiler verbatim allows \input of absolute server paths

🟡 **MEDIUM** · 🔒 security · Status: ✅ done · Confidence: medium (5/5 verifiers) · Effort: M · WS27

**Fix.** Dual defense: (1) compile already forces `openin_any=p` (AIA-03); (2) `.tex`/`.sty`/`.cls` members are deny-scanned for `\write18`, `\openin`, and absolute/pipe/parent-path `\input`/`\include` (brace and brace-less forms) at upload and again in `render_template_bundle` after placeholder substitution so verbatim `[[experience]]` cannot smuggle file-read primitives into the compiler. Relative same-tree includes like `\input{section}` remain allowed.

**Locations:** `backend/app/resumes/template_bundle.py:59` (`render_template_bundle`).

**Evidence.** `_normalize_member_path` blocks zip-slip in member *names*, but `.tex`/`.sty` *content* is only placeholder-substituted and never scanned. A member body of `\input{/etc/passwd}` (or `\input{/app/.env}`) compiles verbatim, and `openin_any` is not forced to restricted (`p`) in `compile.py`.

**Failure scenario.** A user uploads a bundle whose `main.tex` contains `\input{/etc/passwd}`; on generate, TeX reads the file and embeds its contents into the returned PDF — arbitrary server-file disclosure (secrets, cross-tenant data). This is env-dependent on `openin_any`.

**Suggested fix.** Set `openin_any=p` (restrict reads to CWD) via the TeX env for the subprocess, and/or reject `\input`/`\include`/`\write18`/`\openin` of absolute or parent paths in uploaded `.tex` content.

**Verification.** Confirmed 5/5 adversarial verifiers. Verifiers confirmed `_normalize_member_path` guards names only, `.tex` content is never scanned for `\input`, and `compile.py` sets no `openin_any=p`, so the exfiltration path is real (env-dependent); medium is fair.

---

<a id="aia-07"></a>
### AIA-07 — Template upload never scans .tex for \input / \write18 / \openin primitives

🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/46)) · Confidence: high (3/3 verifiers) · Effort: M · WS27

**Fix.** Upload-time deny-scan (layered on AIA-06) now also rejects `\read` and home-path (`~`) `\input`/`\include`, and `validate_resume_template_upload` parses zip bundles so TeX-like members are content-scanned before encryption — not only at `build_resume_template_stored` / render time.

**Locations:** `backend/app/resumes/template_bundle.py:82` (`_read_bundle`) and `:107`; plus `backend/app/services/profile_resume_template.py:15`.

**Evidence.** `_read_bundle` and `validate_resume_template_upload` only check path traversal, extension allow-list, file count, and total size. There is no inspection of `.tex` bytes for `\input{/abs}`, `\write18`, `\openin`, `\read`, or catcode tricks; the decoded body reaches the compiler verbatim. This is the defense-in-depth companion to AIA-06/AIA-03: there is no content gate that would catch a malicious template before the compiler runs.

**Failure scenario.** Even with shell-escape disabled, an absolute-path `\input` still exfiltrates readable server files (AIA-06). With no content gate, there is no defense-in-depth layer catching a malicious template before pdflatex/tectonic runs, so a single misconfiguration (e.g. `openin_any=a`) becomes exploitable.

**Suggested fix.** Add a conservative deny-scan of decoded `.tex` for `\write18`, `\input{` (absolute or `|`pipe), `\openin`, `\read`; combine it with compiler hardening (AIA-03/AIA-06) rather than relying on either alone.

**Verification.** Confirmed 3/3 adversarial verifiers. Verifiers confirmed via grep that no `.tex` byte inspection exists anywhere, and that the compiled PDF is returned to the uploader, so absolute-path `\input` exfiltration currently has no defense layer.

---

<a id="aia-08"></a>
### AIA-08 — Cover-letter prompt embeds untrusted scraped fields with no delimiter or injection guard

⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: S · WS28

**Fix.** Cover-letter LLM prompts fence scraped posting fields and candidate profile data in `<<<JOB_POSTING>>>` / `<<<CANDIDATE_PROFILE>>>` blocks; the system prompt treats those blocks as untrusted data. `CoverLetterService.generate` reuses `looks_like_prompt_injection` on title/company/location/salary/summary/resume_text and forces the offline heuristic when matched (`injection_guarded: true` on the result) — [PR](https://github.com/davidcristian/HeadStart/pull/135).

**Locations:** `backend/app/cover_letters/prompts.py:18` (`user_prompt`) and `:24`; plus `backend/app/services/cover_letters.py:90`.

**Evidence.** `job_title`/`company`/`location`/`job_summary` (scraped, untrusted) and `resume_text` are interpolated inline after instruction lines with no fencing and no `looks_like_prompt_injection` guard — unlike the classifier/reply-drafter families, which sanitize inbound content (WS9). `cover_letters.generate` never calls the injection heuristic.

**Failure scenario.** A malicious job posting with injected instructions in the title/description can steer the cover-letter LLM to emit attacker-chosen or off-profile content into a letter the user may auto-submit.

**Suggested fix.** Delimit untrusted posting/profile content from instructions (explicit fenced block) and reuse the shared injection heuristic before the LLM call.

**Verification.** Confirmed 3/3 adversarial verifiers. Verifiers confirmed only reply_drafts applies the guard; this is a real defense-in-depth gap, low severity fair.

---

<a id="aia-10"></a>
### AIA-10 — LaTeX subprocess has a wall-clock timeout but no CPU / memory / process limits

⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: M · WS27

**Fix.** `_run_compiler_workspace` passes a POSIX `preexec_fn` that applies `RLIMIT_AS` (512 MiB), `RLIMIT_CPU` (ceil of the compile timeout), and `RLIMIT_NPROC` (512) before `tectonic`/`pdflatex` exec; wall-clock `timeout` is unchanged. Non-POSIX hosts skip `preexec_fn`.

**Locations:** `backend/app/resumes/compile.py:84` (`_run_compiler_workspace`).

**Evidence.** `subprocess.run` passes `timeout` only; there is no `preexec_fn`/rlimits, no `ulimit`, no cgroup. A user template with a memory-bomb macro (deep expansion, huge `\count` loop) can consume RAM/CPU for up to the timeout (default 60s) across concurrent compiles. Upload validation checks only size/UTF-8.

**Failure scenario.** Several users trigger generate with pathological templates → worker RAM/CPU exhaustion (DoS) despite the per-compile timeout, since nothing bounds memory or forked helper processes.

**Suggested fix.** Apply `RLIMIT_AS`/`RLIMIT_CPU`/`RLIMIT_NPROC` via `preexec_fn` (or run under a memory-capped sandbox/container); keep the timeout.

**Verification.** Confirmed 3/3 adversarial verifiers. Verifiers confirmed raw compilation with only a wall-clock timeout and no RLIMIT/cgroup — a real DoS hardening gap.

---

<a id="aia-11"></a>
### AIA-11 — LaTeX subprocess inherits the full parent environment, exposing secrets to the compiler

⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: S · WS27

**Fix.** `_run_compiler_workspace` already passes `env=_compiler_env()` (shipped with AIA-03 in `0135f08`): only `PATH` / `HOME` / `TMPDIR`/`TEMP`/`TMP` / `LANG`/`LC_ALL` are copied from the parent, then TeX policy vars (`openin_any=p`, `openout_any=p`, `shell_escape=f`) are forced. App secrets (`JWT_SECRET`, `CREDENTIALS_SECRET_KEY`, DB/provider keys) and host `TEXMF*` overrides are never forwarded. Tracker close adds a dedicated allowlist regression plus tectonic-path secret assertions and documents the allowlist in `docs/modules/profile.md` — [PR](https://github.com/davidcristian/HeadStart/pull/133).

**Locations:** `backend/app/resumes/compile.py:84` and `:92` (`_run_compiler_workspace`).

**Evidence.** Both `subprocess.run` calls omit `env=`, so pdflatex/tectonic inherit the API process environment (`JWT_SECRET`, `CREDENTIALS_SECRET_KEY`, DB creds, provider keys). Combined with untrusted template input, this widens the blast radius of any shell-escape/`\input` primitive.

**Failure scenario.** If any shell-escape path is reachable (AIA-03), the untrusted template runs with the full app environment; an env-reading TeX package or `\write18` discloses server secrets.

**Suggested fix.** Pass an explicit minimal `env=` (`PATH`, `HOME`/`TMPDIR`, `TEXMF*`, `openin_any`/`openout_any=p`) to `subprocess.run` so the compiler cannot read app secrets.

**Verification.** Confirmed 3/3 adversarial verifiers. A real defense-in-depth secret-exposure gap gated on a shell-escape primitive; low is fair.

---

<a id="aia-12"></a>
### AIA-12 — PDF name via replace('.tex','.pdf') replaces every occurrence, mis-deriving output

⚪ **LOW** · 🐞 bug · Status: ✅ done (WS26) · Confidence: high (5/5 verifiers) · Effort: XS · WS26

**Fix.** Both sites now derive the name via `_pdf_output_name()` = `Path(entrypoint).with_suffix('.pdf').name`, which swaps only the final suffix and returns the basename (also repairing nested entrypoints, which the previous join mis-located). Regression test drives a `report.tex.tex` entrypoint.

**Locations:** `backend/app/resumes/compile.py:109` (`_run_compiler_workspace`) and `:50`.

**Evidence.** `pdf_name = entrypoint.replace('.tex', '.pdf')` replaces all occurrences: `notes.tex.tex` → `notes.pdf.pdf`, `my.texfile.tex` → `my.pdffile.pdf`. The compiler's jobname strips only the final extension, so the code then looks for a PDF the compiler never wrote and returns `None` even though the run succeeded.

**Failure scenario.** A bundle whose resolved single-`.tex` entrypoint contains `.tex` more than once compiles fine but is reported as producing no PDF, surfacing a spurious "Could not compile" error.

**Suggested fix.** Derive the name from the stem: `Path(entrypoint).with_suffix('.pdf').name`, not a substring replace.

**Verification.** Confirmed 5/5 adversarial verifiers. `_resolve_entrypoint` can return an arbitrary single-`.tex` filename, so the mangling is reachable; low is correct.

---

<a id="aia-13"></a>
### AIA-13 — Scraped job match-summary flows into resume/cover-letter LLM prompts without an injection heuristic

⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: S · WS28

**Fix.** Resume LLM prompts fence scraped posting + profile data (`<<<JOB_POSTING>>>` / `<<<CANDIDATE_PROFILE>>>`); `ResumeService` reuses `looks_like_prompt_injection` and forces the heuristic curator when matched (`injection_guarded` on the ready result). Cover-letter side already closed by AIA-08.

**Locations:** `backend/app/resumes/prompts.py:34` (`user_prompt`); plus `backend/app/cover_letters/prompts.py:28`.

**Evidence.** `ctx.job_summary` (derived from scraped/LLM job text) is interpolated into the user prompt with no injection sanitization, unlike the reply-drafter path hardened in WS9; title/company/location/salary are likewise raw. (Note: the finding's original "unbounded" framing is imprecise — a 1000-char DB cap exists — but the injection-heuristic gap is real.)

**Failure scenario.** A malicious job posting embeds instructions in title/summary → the LLM overrides "use only profile facts" and fabricates or leaks content into the candidate's auto-generated resume/cover letter, which may then be auto-submitted.

**Suggested fix.** Cap `job_summary`/title length and run the same sanitize/injection heuristic used for reply drafts (`email_classifiers/sanitize.py`) before building the prompt.

**Verification.** Confirmed 3/3 adversarial verifiers. Verifiers confirmed `reply_drafts.py:93` applies the WS9 guard while resumes/cover_letters do not; low is fair.

---

<a id="aia-14"></a>
### AIA-14 — Resume LLM prompt ships candidate email to the provider while the cover-letter prompt omits it

⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: S · WS28

**Fix.** Resume curation `user_prompt` no longer emits `- Email:`; contact email/phone stay off the LLM wire (aligned with cover-letter prompts). `parse_curated_json` still merges email from the stored profile into the rendered resume. Privacy policy + `profile.md` / `frontend.md` document the reduced PII surface.

**Locations:** `backend/app/resumes/prompts.py:40` (`user_prompt`); plus `backend/app/cover_letters/prompts.py:34`.

**Evidence.** The resume `user_prompt` emits `- Email: {profile.email}` to the LLM provider; the sibling cover-letter `user_prompt` sends no email. Two adapters hitting the same providers expose a different PII surface, and neither gates on consent or redacts direct identifiers.

**Failure scenario.** A user on the LLM tier has their email (a direct identifier) sent to a third-party model provider during resume curation but not during cover-letter generation — inconsistent, undocumented PII egress.

**Suggested fix.** Align the PII surface across the two prompt builders and document/gate which identifiers are sent to external providers (data minimisation).

**Verification.** Confirmed 3/3 adversarial verifiers. Verifiers confirmed the asymmetry; low is appropriate (the user's own email, LLM-tier consented).

---

<a id="aia-16"></a>
### AIA-16 — profiles._encode/_decode use function-local `import json`, breaking module convention

⚪ **LOW** · 🔁 consistency · Status: ✅ done (WS26) · Confidence: high (3/3 verifiers) · Effort: XS · WS26

**Fix.** `import json` hoisted to module scope; both function-local imports removed.

**Locations:** `backend/app/services/profiles.py:239` (`ProfileService._encode`) and `:253` (`_decode`).

**Evidence.** Both static methods do `import json` inside the function body. Sibling `tailored_resume.py` and the rest of the codebase import stdlib at module top, and no import cycle justifies a deferred import here. Two copies of the same local import is drift.

**Failure scenario.** No runtime impact; style/consistency drift that makes the encrypt/decrypt path read as if there were an import concern when there is none.

**Suggested fix.** Hoist `import json` to the module top like every sibling service.

**Verification.** Confirmed 3/3 adversarial verifiers. Genuine style drift with no import cycle; low is fair.

---

<a id="aia-17"></a>
### AIA-17 — _validate_pdf reads module `default_settings`, not injected `self._settings`, for the size cap

⚪ **LOW** · 🔁 consistency · Status: ✅ done (WS26) · Confidence: high (3/3 verifiers) · Effort: XS · WS26

**Fix.** `_validate_pdf` is now an instance method reading `self._settings.profile_resume_max_bytes`, matching the rest of the service; a test asserts an injected `profile_resume_max_bytes` is honored.

**Locations:** `backend/app/services/resumes.py:163` (`ResumeService._validate_pdf`).

**Evidence.** `max_bytes = int(getattr(default_settings, 'profile_resume_max_bytes', ...))` uses the module-global `default_settings`, while the rest of the service (`_compile_pdf`, timeout, enabled flag) honors injected `self._settings`. It is also a `@staticmethod`, so it cannot read the instance override.

**Failure scenario.** A caller injecting a `Settings` with a different `profile_resume_max_bytes` gets the wrong output-size limit enforced on compiled resumes; the injected config is silently ignored here, and no test catches it.

**Suggested fix.** Make `_validate_pdf` an instance method reading `self._settings`, consistent with the other config lookups.

**Verification.** Confirmed 3/3 adversarial verifiers. A real consistency defect (2 duplicate reports); low is fair.

---

<a id="aia-18"></a>
### AIA-18 — Summarizer / cover-letter LLM prompts embed scraped fields with no injection guard

⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: M · WS28

**Fix.** Summarizer LLM prompts fence scraped title/company/location in `<<<JOB_POSTING>>>` / `<<<END_JOB_POSTING>>>`; the system prompt treats that block as untrusted data. `SummaryService.annotate` reuses `looks_like_prompt_injection` on those fields and forces the offline heuristic when any posting in the batch matches. Cover-letter side already closed by AIA-08 — [PR](https://github.com/davidcristian/HeadStart/pull/138).

**Locations:** `backend/app/summarizers/adapters/openai.py:76` (`_user_prompt`); plus `backend/app/cover_letters/prompts.py:15`, `backend/app/services/summaries.py:47`, `backend/app/services/cover_letters.py:58`.

**Evidence.** `_user_prompt`/`user_prompt` splice scraped `JobPosting.title`/`company`/`location`/`job_summary` into the LLM message as `- Title: {job.title}` with no fencing and no `looks_like_prompt_injection` gate. WS9 hardened only reply_drafters/email_classifiers; these two families stayed unsanitized (`SummaryService.annotate` does not call the guard).

**Failure scenario.** An attacker-controlled posting on a scraped board injects instructions in the title/summary; the summarizer/cover-letter LLM follows them, corrupting the displayed blurb or generated letter for that user.

**Suggested fix.** Delimit untrusted posting fields from instructions and run the shared injection heuristic before the LLM (as `reply_drafts.draft` does), degrading to the heuristic path on a match.

**Verification.** Confirmed 3/3 adversarial verifiers. Verifiers confirmed the WS9 guard is genuinely absent on this path. (Closely related to AIA-20, which anchors the same summarizer prompt at line 80 across all four provider adapters.)

---

<a id="aia-19"></a>
### AIA-19 — LLM adapters POST via raw httpx with no SSRF / outbound-URL guard

⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (2/3 verifiers) · Effort: M · WS28

**Fix.** Shared `app.ai.llm_common.llm_post` routes every hosted LLM adapter POST through `pinned_request` (same SSRF + DNS-pin policy as scrapers/notifiers). Loopback remains allowed only in `local`/`test` for llama.cpp — [PR](https://github.com/davidcristian/HeadStart/pull/139).

**Locations:** `backend/app/summarizers/adapters/openai.py:52` (`OpenAISummarizer.summarize`); plus `backend/app/cover_letters/adapters/openai.py:38`, `backend/app/email_classifiers/adapters/anthropic.py:41`, `backend/app/reply_drafters/adapters/gemini.py:37`, `backend/app/summarizers/adapters/llamacpp.py:44`.

**Evidence.** Every LLM adapter builds a URL from `*_base_url` settings and calls `self._client.post(url, ...)` directly; none call `assert_safe_outbound_url`, the SSRF guard WS3/WS6 added to `scrapers/http.py`. Base URLs are config-only (env, not user-overridable), so the risk is defense-in-depth.

**Failure scenario.** If a base_url env var is ever misconfigured or attacker-influenced (e.g. future per-user endpoint support), outbound requests to internal hosts are unguarded, sending API keys to an SSRF target.

**Suggested fix.** Route adapter POSTs through the shared safe HTTP helper (or `assert_safe_outbound_url`) so LLM egress inherits the same SSRF policy as scrapers.

**Verification.** Confirmed 2/3 adversarial verifiers (1 refuted). The refuting verifier noted base URLs are env-only with no current exploit path; the finding honestly scopes itself as defense-in-depth low.

---

<a id="aia-20"></a>
### AIA-20 — Summarizer feeds scraped title/company into the LLM prompt unsanitized (all provider adapters)

⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (5/5 verifiers) · Effort: S · WS28 (same defect as AIA-18)

**Fix.** Closed with AIA-18: shared fenced prompts + `SummaryService` injection guard forcing heuristic — [PR](https://github.com/davidcristian/HeadStart/pull/138).

**Locations:** `backend/app/summarizers/adapters/openai.py:80` (`_user_prompt`); plus the sibling adapters:
- `backend/app/summarizers/adapters/anthropic.py:64`
- `backend/app/summarizers/adapters/gemini.py:51`
- `backend/app/summarizers/adapters/llamacpp.py:58`

**Evidence.** `_user_prompt` interpolates `job.title`/`company`/`location` (from untrusted scraped HTML/JSON) directly into the LLM user message with no `sanitize`/`looks_like_prompt_injection` guard, unlike the WS9-hardened reply-drafter path. The same pattern is repeated across all four summarizer provider adapters. (Systemic sibling of AIA-18, which anchors the same defect at the service/prompt-building level.)

**Failure scenario.** A malicious job posting embeds instructions in its title; the LLM emits attacker-chosen text as the stored "why this matches" blurb shown in notifications and the feed. Non-actionable but content-injecting.

**Suggested fix.** Run scraped fields through the shared `sanitize`/`looks_like_prompt_injection` helper before building the summary prompt, mirroring `reply_drafts`.

**Verification.** Confirmed 5/5 adversarial verifiers. Impact is content injection into a one-sentence blurb only, so low is correct.
