# Module: Inbox (mailbox connectors)

**Path:** `backend/app/inbox/`

Dev-only mailbox connectors for Phase 20 application-pipeline automation.
Recruiter replies land in email, not in the app — this subsystem reads and sends
mail, classifies recruiter threads, routes folders, drafts follow-ups, and
supports interview handoff (all behind `INBOX_AGENT_ENABLED`).

**Do not enable on hosted multi-tenant production.** Gate with
`INBOX_AGENT_ENABLED=true` (local/self-hosted dev only). See
[adr/0011-inbox-dev-only.md](../adr/0011-inbox-dev-only.md).

## Contract

```python
# app/inbox/types.py
class MailboxContext(BaseModel):
    connector_type: str      # e.g. "imap_smtp"
    config: MailboxConfig    # IMAP + SMTP host/user/password
    user_id: int | None = None

# app/inbox/base.py
class MailboxConnector(ABC):
    def fetch_messages(self, ctx, *, since_uid=None, limit=50) -> FetchResult: ...
    def send_message(self, ctx, message: OutboundMessage) -> SendResult: ...
    def test_connection(self, ctx) -> ConnectionTestResult: ...
```

## Registry

Adapters self-register with `@register_mailbox("key")`. Modules are imported in
`app/inbox/adapters/__init__.py`; resolve with `get_mailbox(type)`.

## imap_smtp adapter

**Key:** `imap_smtp`. Uses Python stdlib `imaplib` + `smtplib`.

- **Fetch:** `UID SEARCH` + `UID FETCH (RFC822)` on the configured mailbox
  (default `INBOX`); returns normalized `InboxMessage` rows.
- **Send:** plain-text SMTP with optional `In-Reply-To` / `References` for
  threading.
- **Test:** IMAP `SELECT` + SMTP `NOOP` without reading mail.

Config shape matches `MailboxConfig` in `app/inbox/types.py` (IMAP host/port/SSL,
SMTP host/port/TLS, credentials, optional `smtp_from`).

## gmail adapter

**Key:** `gmail`. Uses Google OAuth 2.0 and the Gmail REST API (`httpx`).

- **Connect:** `GET /inbox/gmail/authorize` (auth required) returns a Google consent
  URL; `GET /inbox/gmail/callback` exchanges the code and stores encrypted tokens on
  `mailbox_credential` (`connector_type=gmail`).
- **Fetch:** `users.messages.list` (INBOX, `after:` narrows the scan past the
  cursor) + `users.messages.get`. The `uid` poll cursor is derived from each
  message's `internalDate` (time-ordered), since Gmail ids are not chronological
  and sorting by id could permanently skip later-arriving mail. The raw Gmail id
  rides on the message headers so routing needn't reverse it out of the uid. All
  inbox `uid` columns are `BigInteger`.
- **Send:** `users.messages.send` with a base64url-encoded MIME payload.
- **Move / route:** `users.labels.create` (when missing) + `users.messages.modify`
  (add label, remove INBOX).
- **Test:** `users.getProfile` and match `emailAddress` to the stored credential.

**Operator env** (all required for OAuth):

- `GMAIL_OAUTH_CLIENT_ID`
- `GMAIL_OAUTH_CLIENT_SECRET`
- `GMAIL_OAUTH_REDIRECT_URI` — e.g. `http://localhost:8000/api/v1/inbox/gmail/callback`

Token refresh runs automatically before fetch/send when the access token is near
expiry (`app/inbox/gmail_oauth.py`).

## outlook adapter

**Key:** `outlook`. Uses Microsoft identity OAuth 2.0 and Microsoft Graph mail APIs
(`httpx`).

- **Connect:** `GET /inbox/outlook/authorize` (auth required) returns a Microsoft
  consent URL; `GET /inbox/outlook/callback` exchanges the code and stores encrypted
  tokens on `mailbox_credential` (`connector_type=outlook`).
- **Fetch:** `GET /me/mailFolders/inbox/messages` (ordered by `receivedDateTime`) +
  `GET /me/messages/{id}/$value` for RFC 822 MIME; Graph message ids are stored in
  `raw_headers["x-ms-graph-id"]` and in classification `payload.graph_message_id` for
  folder routing.
- **Send:** `POST /me/sendMail` with a plain-text body and optional threading headers.
- **Move / route:** `mailFolders` lookup/create for nested paths (e.g.
  `HeadStart/General`) + `POST /me/messages/{id}/move`.
- **Test:** `GET /me` and match `mail` / `userPrincipalName` to the stored credential.

**Operator env** (all required for OAuth):

- `OUTLOOK_OAUTH_CLIENT_ID` — Azure app registration application (client) ID
- `OUTLOOK_OAUTH_CLIENT_SECRET` — client secret value
- `OUTLOOK_OAUTH_REDIRECT_URI` — e.g. `http://localhost:8000/api/v1/inbox/outlook/callback`

**Azure app registration (summary):**

1. Register an app in [Microsoft Entra admin center](https://entra.microsoft.com/)
   (or Azure Portal → App registrations).
2. Add redirect URI **Web** → `OUTLOOK_OAUTH_REDIRECT_URI`.
3. Under **API permissions**, add Microsoft Graph delegated permissions:
   `Mail.Read`, `Mail.ReadWrite`, `Mail.Send`, and `User.Read` (plus `offline_access`
   via the OAuth scope list).
4. Create a client secret and copy it to `OUTLOOK_OAUTH_CLIENT_SECRET`.

Token refresh runs automatically before fetch/send when the access token is near
expiry (`app/inbox/outlook_oauth.py`).

## yahoo adapter

**Key:** `yahoo`. Uses Yahoo identity OAuth 2.0 and IMAP/SMTP with SASL
OAUTHBEARER (`imap.mail.yahoo.com` / `smtp.mail.yahoo.com`). Yahoo does not
publish a Gmail/Graph-style REST API — mail access is over standard protocols.

- **Connect:** `GET /inbox/yahoo/authorize` (auth required) returns a Yahoo consent
  URL; `GET /inbox/yahoo/callback` exchanges the code and stores encrypted tokens on
  `mailbox_credential` (`connector_type=yahoo`).
- **Fetch:** IMAP `UID SEARCH` + `UID FETCH (RFC822)` on the `Inbox` folder.
- **Send:** SMTP with `AUTH OAUTHBEARER` after `STARTTLS`.
- **Move / route:** IMAP `UID MOVE` (or COPY/STORE/EXPUNGE fallback) into folders
  created on demand (same contract as `imap_smtp`).

**Operator env** (all required for OAuth):

- `YAHOO_OAUTH_CLIENT_ID` — Yahoo Developer Network app client ID
- `YAHOO_OAUTH_CLIENT_SECRET` — client secret
- `YAHOO_OAUTH_REDIRECT_URI` — e.g. `http://localhost:8000/api/v1/inbox/yahoo/callback`

**Yahoo app registration (summary):**

1. Request commercial Mail API access via [Yahoo Developer Network](https://developer.yahoo.com/)
   (commercial access agreement may be required for production use).
2. Create an app and add redirect URI **Web** → `YAHOO_OAUTH_REDIRECT_URI`.
3. Enable Mail permissions with **Read/Write** scope (`mail-w` in the OAuth request;
   do not combine `mail-r` and `mail-w`).
4. Copy client ID and secret to `YAHOO_OAUTH_CLIENT_ID` / `YAHOO_OAUTH_CLIENT_SECRET`.

Token refresh runs automatically before fetch/send when the access token is near
expiry (`app/inbox/yahoo_oauth.py`).

## fastmail adapter

**Key:** `fastmail`. Uses a Fastmail API token and the JMAP mail/submission APIs
(`httpx`).

- **Connect:** Settings → Inbox → enter Fastmail email + API token; stored on
  `mailbox_credential` (`connector_type=fastmail`) via `PUT /inbox/credentials`.
- **Fetch:** JMAP `Email/query` (inbox role) + `Email/get` for headers and body.
- **Send:** JMAP `Email/set` (draft) + `EmailSubmission/set`.
- **Move / route:** JMAP `Email/set` updates `mailboxIds`; destination mailboxes
  are created with `Mailbox/set` when missing (same folder names as IMAP routing).

**User setup:**

1. In Fastmail → Settings → Privacy & Security → **API tokens**, create a token
   with **Mail** and **Submission** scopes.
2. In HeadStart Settings → Inbox, enter your Fastmail address and paste the token.

No operator env vars are required — auth is per-user. `imap_smtp` remains the
generic fallback for providers that expose IMAP.

## Credential storage

Per-user encrypted row in `mailbox_credential` (one per account). Passwords are
write-only — `MailboxCredentialRead` exposes host/user metadata only.

**Service:** `InboxService` (`app/services/inbox.py`) encrypts on write, resolves
`MailboxContext` for fetch/send/test, and raises `InboxNotEnabledError` when
`INBOX_AGENT_ENABLED` is false.

**Dev fallback:** when `INBOX_USE_ENV_CREDENTIALS=true` and all `INBOX_*` env
vars are set, users without a saved credential share the env mailbox (single-user
local dev only).

`imap_smtp` remains the generic connector for any provider that exposes IMAP.

## API (prefix `/api/v1/inbox`)

All routes require auth and `INBOX_AGENT_ENABLED=true`.

| Method | Path              | Purpose                                      |
| ------ | ----------------- | -------------------------------------------- |
| GET    | `/credentials`    | Read saved mailbox metadata                  |
| PUT    | `/credentials`    | Upsert encrypted IMAP/SMTP or Fastmail token settings |
| DELETE | `/credentials`    | Remove saved credentials                     |
| GET    | `/gmail/authorize`| Start Gmail OAuth (returns consent URL)      |
| GET    | `/gmail/callback` | OAuth redirect (stores Gmail tokens)         |
| GET    | `/outlook/authorize`| Start Outlook OAuth (returns consent URL)  |
| GET    | `/outlook/callback` | OAuth redirect (stores Outlook tokens)     |
| GET    | `/yahoo/authorize`| Start Yahoo OAuth (returns consent URL)      |
| GET    | `/yahoo/callback` | OAuth redirect (stores Yahoo tokens)         |
| POST   | `/test`           | Test IMAP + SMTP (optional inline config)    |
| GET    | `/messages`       | Fetch inbound messages (`since_uid`, `limit`)|
| POST   | `/classify`       | Classify one message (body or mailbox `uid`) |
| GET    | `/classifications`| List recent persisted classifications        |
| GET    | `/routing`        | Read label→folder routing settings           |
| PUT    | `/routing`        | Update label→folder routing settings         |
| POST   | `/route`          | Move a classified message to its folder      |
| POST   | `/draft-reply`    | Draft a recruiter follow-up (dry-run preview; may queue auto-send) |
| GET    | `/reply-drafts`   | List persisted reply drafts                    |
| GET    | `/reply-send-logs`| List audit rows for auto reply decisions       |

`GET /meta` includes `mailboxes` (registered connector keys) and
`inbox_agent_enabled`.

## Email classification (Phase 20c)

**Path:** `backend/app/email_classifiers/`

Pluggable classifiers label inbound recruiter email tied to known applications.
Labels: `general`, `rejection`, `follow_up`, `interview_request`,
`self_ghost_archive`, `out_of_scope`.

- **Registry:** `@register_email_classifier("key")`; resolve with
  `get_email_classifier(key)`.
- **Heuristic default:** keyword/header rules (offline); used for free-tier users
  and as LLM fallback.
- **LLM providers:** `openai`, `gemini`, `anthropic`, `llamacpp` — selected via
  `resolve_ai_settings(..., "email_classify")` (Pro users can override per-purpose
  in Settings → AI models).
- **Sanitization:** HTML stripped, body capped (`EMAIL_CLASSIFY_MAX_BODY_CHARS`);
  obvious prompt-injection patterns map to `out_of_scope`.
- **Thread linking:** `app/services/inbox_linking.py` scores employer domain,
  job title/company mentions, and optional `In-Reply-To` against
  `application_log.payload`.
- **Persistence:** `inbox_classification` table (one row per user + mailbox UID);
  `EmailClassificationService` orchestrates classify + link + store.

## Folder / label routing (Phase 20c)

After classification, routable labels can be moved into configured IMAP folders
(Gmail labels and Outlook folders are exposed as IMAP mailboxes).

- **Config:** `routing_config` JSON on `mailbox_credential` (`enabled`,
  `auto_route_on_classify`, `auto_reply_enabled`, `label_folders`, optional
  `sender_allowlist`). Defaults:
  `HeadStart/General`, `HeadStart/Rejections`, `HeadStart/Ghost`.
- **`out_of_scope`** is never routed (stays in the source mailbox).
- **Connector:** `MailboxConnector.move_message` on `imap_smtp` (UID MOVE when
  supported, otherwise COPY + `\\Deleted` + EXPUNGE). Creates the destination
  mailbox when missing.
- **API:** `GET/PUT /inbox/routing`, `POST /inbox/route` (`classification_id` or
  `message_uid`). Classify auto-routes when routing is enabled.
- **Audit:** `routed_to`, `routing_status` (`moved` / `skipped` / `failed`), and
  `routing_error` on `inbox_classification`.

## Beat orchestration loop (Phase 20f)

When `INBOX_AGENT_ENABLED=true`, beat runs `process_inbox_messages` every
`INBOX_POLL_INTERVAL_SECONDS` (default 300). `InboxOrchestrationService`:

1. Resolves pollable users (enabled `mailbox_credential` rows, plus env-fallback
   users when `INBOX_USE_ENV_CREDENTIALS=true`).
2. Fetches inbound mail since `inbox_poll_state.last_polled_uid` (bootstraps from
   the highest persisted classification UID when unset).
3. Applies `InboxGateService` before classification — only messages tied to active
   or ghosted applications (employer domain, thread headers, ghost self-mail, or
   optional `sender_allowlist`) enter the classifier; unrelated mail is ignored and
   the poll cursor advances past it without LLM calls or DB writes.
4. Classifies gated messages in UID order via `EmailClassificationService` (ghost
   recovery, interview handoff, and folder routing run as on manual classify).
5. Advances the poll cursor through classified and ignored messages; classify
   failures stop the batch so the failed message retries on the next tick.

Batch size per user per tick: `INBOX_POLL_BATCH_SIZE` (default 50). See
[worker.md](worker.md).

**Known gap:** none for the application-scoped gate — unrelated mail is skipped
before classification. See `InboxGateService` in `app/services/inbox_gate.py`.

## Ghost recovery (Phase 20c)

When inbound mail is classified for a **ghosted** application (`seen_job.ghosted_at`
set) and the label is recruiter signal (`general`, `rejection`, `follow_up`,
`interview_request` — not `self_ghost_archive` or `out_of_scope`):

1. Clear `ghosted_at` and set `ghost_recovered_at`.
2. Transition pipeline stage:
   - `interview_request` → `interview_pending` (`interview_pending_at`)
   - `rejection` → `rejected` (`recruiter_rejection_at`)
   - `follow_up` / `general` → `awaiting_reply`
3. Record recovery metadata on `inbox_classification.payload.ghost_recovery`.
4. Send a high-priority alert via the search's notification target (or all user
   targets when the search has none). ntfy uses `priority: high`.

`EmailClassificationService.classify` invokes `GhostRecoveryService` after linking
a job and before folder routing.

## Interview handoff (Phase 20e)

When inbound mail classifies as `interview_request` for a linked, active
application (`status=applied` or a live submitted attempt) that is **not**
ghosted and not already `interview_pending`:

1. Set `seen_job.interview_pending_at`.
2. Record `interview_handoff` metadata on `inbox_classification.payload`.
3. Send a high-priority alert via the search's notification target (or all user
   targets when the search has none). ntfy uses `priority: high`. Alert copy:
   "Interview to schedule at {company} — take over from here".

Ghosted applications still route through `GhostRecoveryService` first; interview
handoff skips when `ghosted_at` is set or `interview_pending_at` is already set.

`EmailClassificationService.classify` invokes `InterviewHandoffService` after
ghost recovery and before folder routing.

## Ghost detection (Phase 20c)

When `INBOX_AGENT_ENABLED=true`, beat runs `detect_ghosted_applications` every
`INBOX_GHOST_CHECK_INTERVAL_SECONDS` (default 3600). `GhostDetectionService`
finds `seen_job` rows with `status=applied`, no `ghosted_at`, and
`applied_at` older than `INBOX_GHOST_WINDOW_DAYS` (default 14). For each stale
application where the user has mailbox credentials:

1. Send a self-addressed summary email (`build_ghost_summary_message` in
   `app/inbox/ghost_message.py`) with `[HeadStart Ghost]` subject prefix and
   `X-HeadStart-Type: ghost`.
2. Set `seen_job.ghosted_at` on successful SMTP send (failed sends are retried
   on the next tick).

The applications pipeline exposes stage `ghosted` when `ghosted_at` is set.
When the summary email returns to the inbox, the existing classifier labels it
`self_ghost_archive` and routing moves it to `HeadStart/Ghost`.

## Follow-ups (Phase 20d)

Autonomous reply drafts build on classification and routing. Drafts are persisted
and previewed immediately; when `auto_reply_enabled` is on, SMTP send is queued
with a human-like delay (see [Response delay queue](#response-delay-queue-phase-20d)).

**Path:** `backend/app/reply_drafters/`

Pluggable drafters produce recruiter follow-up replies for classified inbound mail.
Supported classification labels: `follow_up`, `general`.

- **Registry:** `@register_reply_drafter("key")`; resolve with `get_reply_drafter(key)`.
- **Heuristic default:** template replies from profile `answers` (salary, work auth,
  availability) and job context; offline.
- **LLM providers:** `openai`, `gemini`, `anthropic`, `llamacpp` — selected via
  `resolve_ai_settings(..., "email_draft")` (Pro users can override per-purpose
  in Settings → AI models).
- **Sanitization:** the drafter reuses `email_classifiers/sanitize.py` on the
  stored recruiter subject and `body_excerpt` before either reaches an LLM (HTML
  stripped, text capped). Because this path can auto-send over SMTP, a **subject
  or body** matching instruction-injection patterns bypasses the LLM entirely and
  is drafted by the offline heuristic instead — recorded as `injection_guarded` in
  the draft payload and surfaced in the draft `notes`. Detection runs on the
  sanitized text, so HTML-encoded payloads (e.g. `&#105;gnore…`) are caught.
- **Persistence:** `inbox_reply_draft` table (one row per user + classification);
  `ReplyDraftService` orchestrates draft + store.
- **API:** `POST /inbox/draft-reply` (`classification_id` or `message_uid`,
  optional `regenerate`); `GET /inbox/reply-drafts` (`seen_job_id` filter).
- **Applications UI:** `/app/applications` shows the latest draft per job and a
  **Draft reply** button when a draftable classification exists.

**Safe-send guardrails:** built-in legal/HR topic blocklist on inbound + draft
text; per-user hourly/daily caps (`INBOX_REPLY_MAX_PER_HOUR`,
`INBOX_REPLY_MAX_PER_DAY`); audit log at `GET /inbox/reply-send-logs` for queue,
send, and blocked decisions. Blocked sends set `inbox_pending_reply.status=blocked`
and leave the draft in `draft` for manual review.

## Response delay queue (Phase 20d)

When `auto_reply_enabled` is true on the user's routing config, each new reply
draft is queued in `inbox_pending_reply` with a `send_after` timestamp. The
delay is `INBOX_REPLY_MIN_DELAY_SECONDS` (default 1800, never below 60) plus
optional random jitter (`INBOX_REPLY_DELAY_JITTER_SECONDS`, default 900).

- **Opt-in:** `auto_reply_enabled` on `GET/PUT /inbox/routing` (default off).
- **Enqueue:** `ReplyDraftService` queues after draft creation; beat orchestration
  auto-drafts for `follow_up` / `general` when auto-reply is on.
- **Preview:** drafts are visible immediately via `GET /inbox/reply-drafts`; only
  SMTP send waits for the delay window.
- **Send:** beat task `process_pending_replies` every
  `INBOX_REPLY_SEND_INTERVAL_SECONDS` (default 60) calls
  `PendingReplyService.process_due` to SMTP-send due rows and mark drafts `sent`.
- **Safe-send:** topic blocklist, hourly/daily caps, and audit log via
  `ReplySafeSendService`; see [Follow-ups (Phase 20d)](#follow-ups-phase-20d).
- **API fields:** `ReplyDraftRead.queue_status` and `send_after` expose queue state.
