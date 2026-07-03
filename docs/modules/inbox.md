# Module: Inbox (mailbox connectors)

**Path:** `backend/app/inbox/`

Dev-only mailbox connectors for Phase 20 application-pipeline automation.
Recruiter replies land in email, not in the app — this subsystem reads and sends
mail so later phases can classify, route, and draft replies.

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

## Credential storage

Per-user encrypted row in `mailbox_credential` (one per account). Passwords are
write-only — `MailboxCredentialRead` exposes host/user metadata only.

**Service:** `InboxService` (`app/services/inbox.py`) encrypts on write, resolves
`MailboxContext` for fetch/send/test, and raises `InboxNotEnabledError` when
`INBOX_AGENT_ENABLED` is false.

**Dev fallback:** when `INBOX_USE_ENV_CREDENTIALS=true` and all `INBOX_*` env
vars are set, users without a saved credential share the env mailbox (single-user
local dev only).

## API (prefix `/api/v1/inbox`)

All routes require auth and `INBOX_AGENT_ENABLED=true`.

| Method | Path              | Purpose                                      |
| ------ | ----------------- | -------------------------------------------- |
| GET    | `/credentials`    | Read saved mailbox metadata                  |
| PUT    | `/credentials`    | Upsert encrypted IMAP/SMTP settings          |
| DELETE | `/credentials`    | Remove saved credentials                     |
| POST   | `/test`           | Test IMAP + SMTP (optional inline config)    |
| GET    | `/messages`       | Fetch inbound messages (`since_uid`, `limit`)|
| POST   | `/classify`       | Classify one message (body or mailbox `uid`) |
| GET    | `/classifications`| List recent persisted classifications        |
| GET    | `/routing`        | Read label→folder routing settings           |
| PUT    | `/routing`        | Update label→folder routing settings         |
| POST   | `/route`          | Move a classified message to its folder      |

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
  `auto_route_on_classify`, `label_folders`). Defaults:
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
3. Classifies each message in UID order via `EmailClassificationService` (ghost
   recovery, interview handoff, and folder routing run as on manual classify).
4. Advances the poll cursor only through successfully classified messages;
   classify failures stop the batch so the message retries on the next tick.

Batch size per user per tick: `INBOX_POLL_BATCH_SIZE` (default 50). See
[worker.md](worker.md).

**Known gap:** the loop currently classifies every fetched message. Personal mail,
newsletters, and other non-application senders are labeled (often `out_of_scope`)
and persisted, but should eventually be **skipped before classification** when
they cannot be linked to an active or ghosted application. See the
*Application-scoped inbox gate* item in [roadmap.md](../roadmap.md).

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

## Follow-ups (Phase 20c+)

Autonomous reply drafts build on classification and routing — see
[roadmap.md](../roadmap.md).
