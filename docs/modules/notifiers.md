# Module: Notifiers

**Path:** `backend/app/notifiers/`

Notifiers deliver new jobs to a channel. Each channel is one self-registering
adapter. Built-in channels: `discord`, `email`, `ntfy`, `slack`, `telegram`, and
`webhook`.

## Contract

```python
# app/notifiers/types.py
class NotifyContext(BaseModel):
    target_type: str      # e.g. "ntfy"
    config: dict          # channel config from the NotificationTarget
    digest: bool = False  # when True, send one batched summary message
    search_name: str | None = None
    locale: str | None = None  # en|de preference; None → DEFAULT_LOCALE (NTF-12)

# app/notifiers/base.py
class Notifier(ABC):
    @abstractmethod
    def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> None: ...
```

## Localization (NTF-12)

User-facing digest titles and email field labels come from
`app/core/i18n.py` (English + German catalogs). Resolution order:
`NotifyContext.locale` (from `user.locale`) → `DEFAULT_LOCALE` → `en`.
Pipeline, digest flush, test-send, and application alerts pass the owner's
locale. Auth emails (`reset` / `verify` / existing-account) use the same
catalog via an optional `locale=` argument. Users set preference with
`PATCH /auth/me` `{ "locale": "en"|"de"|null }`.

## Registry

Adapters self-register with `@register_notifier("key")`, where `key` matches a
`NotificationTarget.type`. Modules are imported in
`app/notifiers/adapters/__init__.py`; resolve with `get_notifier(type)`.

## Write-time config validation (API-14)

`TargetService.create` / `update` call `validate_target_config` so required keys
and outbound URL safety are checked **before** the row is stored — not only
inside `adapter.send`. Missing `topic` / `webhook_url` / `to` / `bot_token` /
`chat_id` raise `ValidationError` (HTTP 422). `webhook_url` and optional ntfy
`server_url` go through `assert_safe_outbound_url` (SSRF defense-in-depth;
private/loopback rejected at save). Ntfy topic guessability remains enforced
(NTF-06). Every registered notifier key must have a validator (unit-tested).

## Match summaries

When a job carries a `summary` (the "why this matches" blurb — see
[summaries.md](summaries.md)), every adapter includes it in the message: an
extra line in `ntfy`/`slack`/`telegram`, a localized `Why this matches:` /
`Warum das passt:` line in `email`, the embed description in `discord`, and a
`summary` field in the `webhook` JSON. This applies to both immediate and
digest sends. When the blurb is empty, output is unchanged.

## ntfy adapter

**Key:** `ntfy`. Config: `{ "server_url": "https://ntfy.sh", "topic": "...",
"priority": "default", "token": "…" }` (`token` optional).

`NTFY_DEFAULT_TOPIC` (and `NTFY_DEFAULT_SERVER_URL`) seed the demo notification
target via `just seed`. Outside `local`/`test`, startup rejects the guessable
`headstart-change-me` placeholder and any topic containing `change-me`; Terraform
similarly requires an explicit unguessable `ntfy_default_topic` with no default
(OPS-16). **NTF-06 / API-14:** `TargetService` rejects empty / `change-me` /
under-16-character topics on create/update (and validates optional `server_url`
against the outbound SSRF policy), and `just seed` replaces a guessable
`NTFY_DEFAULT_TOPIC` with a random `jobs-<16 hex>` topic (logged) so the demo
target never publishes to a public channel. On ntfy.sh the topic name is the
capability — treat it like a secret and prefer an auth token.

For each new job it POSTs JSON to the **server root** (`server_url`) using
ntfy's [JSON publish API](https://docs.ntfy.sh/publish/#publish-as-json)
so non-ASCII titles/messages avoid HTTP-header encoding pitfalls (topic is a
JSON field, not a URL path segment). The body includes:

- `topic`: from config (required)
- `title`: `"<title> @ <company>"`
- `message`: summary / location / apply URL lines (when present)
- `priority`: numeric map of config `min|low|default|high|max` → 1–5
- `tags`: e.g. `["briefcase"]`
- `click`: the job URL when it is absolute http(s) (non-http schemes omitted; NTF-08)

When `token` is set, the request also sends `Authorization: Bearer <token>` for
protected topics. Sends are best-effort per job and recorded in `delivery_log`
with status/error. In digest mode, one batched push lists every new job in the
window (same JSON shape; `click` omitted). The `server_url` is validated against
private/loopback addresses (SSRF protection) and the POST is DNS-pinned (single
resolve, connect by IP with Host/SNI). On HTTP failure, `server_url` / topic /
auth token are redacted from `DeliveryResult.error` and warning logs before
persist (NTF-10).

## email adapter

**Key:** `email`. Config: `{ "to": "you@example.com" }`.

Uses the app-wide `SMTP_*` settings (same as password reset). Sends one
plain-text email per new job with subject `"<title> @ <company>"` and body
lines for company, location, and apply URL.

When SMTP is not configured, deliveries are recorded as `failed` with a clear
error (unlike password reset, which logs the link in dev). Digest mode sends
one email listing all jobs in the batch.

## Digest mode

Set a search's `notification_mode` to `digest` and choose
`digest_interval_seconds` (minimum 60). New jobs queue in `pending_digest` via
one batched insert/flush per scrape (not one flush per job). The beat task
`flush_due_digests` sends one batched message per search when the
interval elapses. Every adapter formats a summary title (e.g. `5 new jobs —
Google SWE`) and lists each posting. `delivery_log` still records one row per
job. After send (or when the notifier is not allowed on the current plan), the
queue for that search is cleared with one bulk `DELETE` on `search_id`. Each
due search is flushed independently (errors are logged and skipped; successful
flushes commit before the next search) so one misconfigured target cannot block
or duplicate other users' digests.

## slack adapter

**Key:** `slack`. Config: `{ "webhook_url": "https://hooks.slack.com/services/..." }`.

Posts one Slack message per new job via an [incoming webhook](https://api.slack.com/messaging/webhooks).
Create the webhook in your Slack workspace (Apps → Incoming Webhooks), then paste
the URL into the target config. Messages use mrkdwn with title, company,
location, and an Apply link. Scraped title/company/summary/location text is
escaped for Slack mrkdwn (`&`, `<`, `>`), and Apply links are emitted only for
http(s) URLs that cannot break out of `<url|label>` syntax. Digest mode sends
one message listing all jobs. Outbound webhook URLs are validated against
private/loopback addresses (SSRF protection) and POSTs are DNS-pinned via
`pinned_request`. On HTTP failure, the webhook URL is redacted from
`DeliveryResult.error` and warning logs before persist (httpx embeds the
request URL in `str(HTTPError)`).

## discord adapter

**Key:** `discord`. Config: `{ "webhook_url": "https://discord.com/api/webhooks/..." }`.

Posts one Discord message per new job via a [channel webhook](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks).
Create the webhook in your server (Server Settings → Integrations → Webhooks),
then paste the URL into the target config. Messages use a rich embed with title,
company, location, and a clickable apply link. Scraped text is escaped so
markdown link/emphasis metacharacters cannot inject attacker-controlled links;
embed and digest Apply URLs are restricted to http(s). Digest mode uses one
embed with a bullet list. Outbound webhook URLs are validated against
private/loopback addresses (SSRF protection) and POSTs are DNS-pinned via
`pinned_request`. On HTTP failure, the webhook URL is redacted from
`DeliveryResult.error` and warning logs before persist.

## telegram adapter

**Key:** `telegram`. Config: `{ "bot_token": "123456:ABC...", "chat_id": "123456789" }`.

Posts one Telegram message per new job via the [Bot API](https://core.telegram.org/bots/api).
Create a bot with [@BotFather](https://t.me/BotFather), send `/start` to it (or add it to a
group), then use your numeric chat id in config. Messages use HTML formatting with title,
company, location, and an Apply link. Apply `href`s are restricted to http(s) (same
`safe_http_job_url` gate as Slack/Discord) and then HTML-escaped. Digest mode sends one
HTML message listing all jobs. Outbound Bot API calls are DNS-pinned via `pinned_request`
(SSRF defense-in-depth even though the host is fixed). On HTTP failure, the bot token is
redacted from `DeliveryResult.error` and warning logs before persist (the Bot API
embeds the token in the request URL, which httpx includes in `str(HTTPError)`).
Shared helper: `app.notifiers.http_errors.safe_http_error` (also used by
webhook/slack/discord/ntfy — NTF-10).

## webhook adapter

**Key:** `webhook`. Config:

```json
{
  "webhook_url": "https://example.com/hooks/headstart",
  "secret": "optional-hmac-signing-key",
  "headers": { "X-Custom": "value" }
}
```

POSTs machine-readable JSON to any HTTPS endpoint for Zapier, n8n, or custom
integrations. Immediate mode sends one payload per job (`event: job.new`); digest
mode sends one batched payload (`event: jobs.digest` with a `jobs` array). Each
job includes `external_id`, `title`, `company`, `location`, `url`, `summary`
(the match blurb, or `""`), and `posted_at` (ISO-8601 or `null`).

When `secret` is set, requests include an `X-HeadStart-Signature` header with
`sha256=<hex>` (HMAC-SHA256 of the JSON body). Optional `headers` are merged
into the request, but `Content-Type` and `X-HeadStart-Signature` are reserved
(case-insensitive) so user config cannot override the JSON content type or the
HMAC signature. Outbound URLs are validated against private/loopback addresses
(SSRF protection) and POSTs are DNS-pinned via `pinned_request`. On HTTP
failure, the webhook URL is redacted from `DeliveryResult.error` and warning
logs before persist.

## Adding a channel

See [../recipes.md](../recipes.md) → "add a new notification
channel". Test with mocked HTTP/transport; never send real notifications in
tests.
