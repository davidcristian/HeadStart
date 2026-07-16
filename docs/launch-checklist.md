# Public launch checklist

Use this list before inviting strangers to a hosted HeadStart instance. It
complements [deploying-to-aws.md](deploying-to-aws.md) (infrastructure) and
[getting-started.md](getting-started.md) (first user setup).

---

## 1. Domain & HTTPS

- [ ] **Custom domain configured** — set `domain_name` + `route53_zone_id` (or
  `acm_certificate_arn`) in Terraform. **Prod requires this** — plan/apply fails
  without HTTPS (`prod_requires_https`, OPS-36). See
  [deploying-to-aws.md#custom-domain--https](deploying-to-aws.md#custom-domain--https).
- [ ] **`terraform output https_enabled`** is `true` and
  **`terraform output app_url`** shows `https://…`.
- [ ] **DNS resolves** — `curl "$(terraform output -raw app_url)/api/v1/health"`
  returns `{"status":"ok"}` (or equivalent).
- [ ] **`FRONTEND_BASE_URL` matches the public URL** — Terraform sets this
  automatically from `app_url` on ECS tasks. Password-reset links and Stripe
  return URLs depend on it. After changing the domain, run `terraform apply`
  and roll ECS (`just deploy`).

---

## 2. CORS & cookies

- [ ] **`CORS_ORIGINS`** includes your public origin (defaults to `app_url` when
  `domain_name` is set). Add extra origins only if the UI is served from
  another hostname.
- [ ] **Auth cookies match the public scheme** — Terraform sets
  `AUTH_COOKIE_SECURE` from `https_enabled` (`true` with TLS, `false` on the
  default HTTP ALB). Do not force `true` on a plain-HTTP public URL (browsers
  drop the refresh cookie). On a public domain, prefer HTTPS.

---

## 3. Transactional email

Required for password reset and the **email** notification channel.

- [ ] **SMTP relay configured** — set `smtp_host` (+ `smtp_user` /
  `TF_VAR_smtp_password`) in Terraform or via `TF_VAR_*` during
  `just aws-first-deploy`. Password is stored in Secrets Manager.
- [ ] **`SMTP_FROM` uses your domain** — defaults to `noreply@<domain_name>`
  when a custom domain is set. Verify SPF/DKIM (or your provider's domain
  verification) so messages are not spam-foldered.
- [ ] **Send a test** — trigger **Forgot password** for a test account and
  confirm the email arrives with a link on your domain.

Without SMTP, reset links are only logged in CloudWatch (not suitable for public
users).

---

## 4. Legal & trust pages

- [ ] **Privacy** (`/privacy`) and **Terms** (`/terms`) reviewed for your entity.
- [ ] **Impressum** (`/impressum`) — customize placeholder operator details before
  marketing to German users (page and footer link are shipped; see
  [roadmap Phase 10](roadmap.md#phase-10--german-legal-compliance)).
- [ ] **Subprocessors** (`/subprocessors`) accurate if you use Stripe, AI
  providers (OpenAI / Gemini / Anthropic), inbox mailbox OAuth (Gmail / Outlook /
  Yahoo), ads, or external SMTP.
- [ ] **Cookie consent** banner tested (Essential only vs Accept all).

---

## 5. Billing (if charging)

- [ ] **Stripe** env vars set (`STRIPE_SECRET_KEY`, webhook secret, price IDs).
  See [modules/billing.md](modules/billing.md).
- [ ] **Checkout webhook** endpoint reachable at
  `https://<domain>/api/v1/billing/webhook`.
- [ ] **Pricing page** (`/pricing`) reflects your live plans and trial terms.

---

## 6. Core product smoke test

- [ ] Register → onboarding wizard → create source, target, search → **Run now**
  returns jobs or a clear error.
- [ ] Notification delivers on at least one channel (ntfy, email, Slack, …).
- [ ] **Searches page** shows `last_run_at` / `last_error` after a scheduled tick.

---

## 7. Auto-apply (optional — know the limits)

Auto-apply is **off by default** per source (`auto_apply_enabled`). Only enable
after reading [modules/appliers.md](modules/appliers.md).

**Supported adapters (v1):** Greenhouse, Lever, Ashby, Workday, Google Careers,
**Microsoft Careers**, **Amazon Jobs**, **Apple Careers**, **Meta Careers**,
**SmartRecruiters**, **Uber Careers**, **Shopify Careers** (delegates to Ashby),
**Snowflake Careers** (delegates to Ashby), **Indeed** (delegates to those ATS
adapters when the listing's employer apply URL is recognized), and **LinkedIn**
(delegates to those ATS adapters when possible; LinkedIn-hosted Easy Apply is
best-effort). There is **no** apply adapter for generic HTML/Playwright sources.

**Not fully automated — set expectations before launch:**

| Area | Limitation |
| ---- | ---------- |
| **Resume files** | Uploaded on the Application profile (PDF/Word, up to 2 MB). Attached on Greenhouse, Lever, Ashby, Workday, Microsoft Careers, Amazon Jobs, Apple Careers, Meta Careers, Google Careers, **Indeed-hosted** Easy Apply (Base64 `applicant.resume.file`), and **LinkedIn-hosted** Easy Apply (Ambry upload → `fileUploadResponses`) live apply; plain `resume_text` / `resumeText` is a fallback when no file is stored. Dry-run previews include resume metadata and (for Google Careers) the pending Scotty upload URL. |
| **Greenhouse / Lever / Ashby** | Live submit needs an employer-issued API key (Job Board / Postings / Ashby API). Store in encrypted [site credentials](modules/credentials.md), not plain source config. |
| **Workday** | Requires logged-in candidate session cookies. Primary/secondary/supplementary **questionnaires** are submitted when mapped in `profile.answers` (preview via dry run). **Work experience**, **education**, **skills**, and **languages** from the application profile are posted via CXS when present (preview via dry run). Degree, field-of-study, and skill values are resolved against tenant catalogs when session cookies are available; unmatched labels fall back to descriptors. Resume upload uses the stored file when available. Enable `auto_terms_consent` when the employer requires T&C acceptance. |
| **Google Careers** | Requires the candidate's own logged-in Google account cookies plus CSRF token (`session.at`). Dry run resolves the apply URL and mapped Careers profile from the public job detail page. Live submit uploads resume files via Google's Scotty attachment endpoint, then runs the internal batchexecute RPC flow (best-effort; employer questions may need `profile.answers`). |
| **Microsoft Careers** | Requires the candidate's own logged-in session on `apply.careers.microsoft.com` plus optional `session.csrf_token`. Resume uploads via `/api/pcsx/upload_resume` before submit. Country-specific screening/consent questions are best-effort — map `profile.answers` when required. |
| **Amazon Jobs** | Requires the candidate's own logged-in amazon.jobs session cookies. Resume files upload via `POST /api/apply/documents` before `submit_application`. Employer screening questions are best-effort — map `profile.answers` when required. Amazon may block unattended submits with CAPTCHA; preview via dry run first. |
| **Apple Careers** | Requires the candidate's own logged-in jobs.apple.com session cookies plus `session.talent_id` and `session.csrf_token`. Resume files upload via `/api/v1/js/talent/<id>/file/uploadFile` before `applyJob`. Retail roles with store pickers need `config.store_locations`. Employer questionnaires are best-effort — map `profile.answers` when required. |
| **Meta Careers** | Requires the candidate's own logged-in metacareers.com session cookies plus `session.session_id` (browser session key). Resume files upload via Relay multipart on `xcp_create_application_v2`. EEO and employer screening questions are best-effort — map `profile.answers` when required. Meta's AI-assisted apply flow may reject unattended submits; preview via dry run first. |
| **Indeed** | Fetches the viewjob page and delegates to Greenhouse/Lever/Ashby/Workday/Google/Microsoft/Amazon/Meta when the listing embeds a recognized employer apply URL (most Easy Apply jobs). Indeed-hosted Easy Apply (no external ATS) needs logged-in Indeed session cookies and posts to private `smartapply.indeed.com` APIs — set `accept_private_api_risk: true` (Sources UI confirms ToS/ban risk) before auto-apply or live submit. Multi-step questionnaires are best-effort. When the application profile has a stored resume file, Indeed-hosted live submit Base64-embeds it as `applicant.resume.file` (`resumeText` only when no file is stored). Unsupported external URLs (custom career sites, Breezy, etc.) fail with a clear error. |
| **LinkedIn** | Fetches the guest job-posting page and delegates to Greenhouse/Lever/Ashby/Workday/Google/Microsoft/Amazon/Meta when Voyager returns a recognized employer apply URL (offsite listings). LinkedIn-hosted Easy Apply needs logged-in `li_at` + `JSESSIONID` cookies and posts to private Voyager APIs — set `accept_private_api_risk: true` (Sources UI confirms ToS/ban risk) before auto-apply or live submit. Multi-step questionnaires are best-effort — map `profile.answers` when required. When the profile has a stored resume and the form includes a document-upload field, live submit uploads the file to LinkedIn Ambry and includes the asset URN in `fileUploadResponses` (session cookies are omitted on the Ambry PUT; see APL-19). |
| **Custom questions** | Only fields mapped in the application profile (`answers`, config paths) are sent. Unmapped required questions can cause rejection. |
| **Coverage** | Treat auto-apply as a **best-effort preview + submit helper**, not unattended bulk applying. Pipeline auto-apply is capped per plan (`max_auto_applies_per_day`). Always use **dry run / preview** first. |
| **Safety — LinkedIn / Indeed private APIs & credentialed scrape (DOC-12 / XCT-19)** | Hosted Easy Apply drives LinkedIn Voyager and Indeed smartapply with the candidate's own session cookies. The same cookies also power credentialed scrape past auth walls / Cloudflare. LinkedIn and Indeed User Agreements typically prohibit automated access; anti-bot defenses can suspend or ban personal accounts. Operators and users accept this ToS/legal risk themselves — disclose it before launch. Users must acknowledge it in the Credentials UI before saving LinkedIn/Indeed session cookies, and set `accept_private_api_risk` before enabling auto-apply or live submit. Prefer dry-run preview and delegated ATS apply when possible. See [scrapers.md](modules/scrapers.md#linkedin--indeed-credentialed-scrape-tos-risk-xct-19). |

Before advertising auto-apply:

- [ ] Test **preview** (`dry_run`) and a live apply on each ATS you support.
- [ ] Confirm `application_log` rows appear under **Application profile**.
- [ ] Leave `auto_apply_enabled` off until operators understand the limits above.
- [ ] For LinkedIn/Indeed sources, confirm operators and users understand the
  credentialed-scrape and private-API / account-ban risk above before saving
  session cookies or enabling auto-apply.

---

## 8. Operations

- [ ] **Secrets backed up** — `.aws-first-deploy-secrets.env` and Stripe keys
  stored safely; they cannot be recovered from Terraform output alone.
- [ ] **Metrics** — scrape API `/metrics` and worker `:9090/metrics` if you run
  Prometheus ([modules/metrics.md](modules/metrics.md)).
- [ ] **Runbook** — operators know how to tail CloudWatch logs and run
  `just deploy` for rollouts ([runbook.md](runbook.md)).

---

## Quick reference: Terraform vars for a branded launch

```hcl
domain_name       = "jobs.example.com"
route53_zone_id   = "Z0123456789ABCDEFGHIJ"
smtp_host         = "email-smtp.us-east-2.amazonaws.com"
smtp_user         = "AKIA..."
# smtp_password via TF_VAR_smtp_password (Secrets Manager)
# smtp_from       = "noreply@jobs.example.com"  # optional; defaults from domain
```

Or with `just aws-first-deploy`:

```bash
just aws-first-deploy PREFIX=yourname \
  DOMAIN_NAME=jobs.example.com \
  ROUTE53_ZONE_ID=Z0123456789ABCDEFGHIJ \
  TF_VAR_smtp_host=email-smtp.us-east-2.amazonaws.com \
  TF_VAR_smtp_user=AKIA... \
  TF_VAR_smtp_password='...' \
  YES=1
```

After apply: `eval "$(just aws-deploy-env)" && just deploy`, then work through
the checklist above.
