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

| Method | Path           | Purpose                                      |
| ------ | -------------- | -------------------------------------------- |
| GET    | `/credentials` | Read saved mailbox metadata                  |
| PUT    | `/credentials` | Upsert encrypted IMAP/SMTP settings          |
| DELETE | `/credentials` | Remove saved credentials                     |
| POST   | `/test`        | Test IMAP + SMTP (optional inline config)    |
| GET    | `/messages`    | Fetch inbound messages (`since_uid`, `limit`)|

`GET /meta` includes `mailboxes` (registered connector keys) and
`inbox_agent_enabled`.

## Follow-ups (Phase 20c+)

Email classification, folder routing, ghost detection, and the Celery beat
orchestration loop are separate roadmap items — they build on this connector.
