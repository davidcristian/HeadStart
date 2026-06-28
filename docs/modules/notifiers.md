# Module: Notifiers

**Path:** `backend/app/notifiers/`

Notifiers deliver new jobs to a channel. Each channel is one self-registering
adapter. Built-in channels: `discord`, `email`, `ntfy`, `slack`, and `telegram`.

## Contract

```python
# app/notifiers/types.py
class NotifyContext(BaseModel):
    target_type: str      # e.g. "ntfy"
    config: dict          # channel config from the NotificationTarget
    digest: bool = False  # when True, send one batched summary message
    search_name: str | None = None

# app/notifiers/base.py
class Notifier(ABC):
    @abstractmethod
    def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> None: ...
```

## Registry

Adapters self-register with `@register_notifier("key")`, where `key` matches a
`NotificationTarget.type`. Modules are imported in
`app/notifiers/adapters/__init__.py`; resolve with `get_notifier(type)`.

## ntfy adapter

**Key:** `ntfy`. Config: `{ "server_url": "https://ntfy.sh", "topic": "...",
"priority": "default" }`.

For each new job it POSTs to `{server_url}/{topic}` with headers:

- `Title`: `"<title> @ <company>"`
- `Priority`: from config (`min|low|default|high|max`)
- `Tags`: e.g. `briefcase`
- `Click`: the job URL (tap-through)

Sends are best-effort per job and recorded in `delivery_log` with status/error.
In digest mode, one batched push lists every new job in the window.

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
`digest_interval_seconds` (minimum 60). New jobs queue in `pending_digest`;
the beat task `flush_due_digests` sends one batched message per search when the
interval elapses. Every adapter formats a summary title (e.g. `5 new jobs —
Google SWE`) and lists each posting. `delivery_log` still records one row per
job.

## slack adapter

**Key:** `slack`. Config: `{ "webhook_url": "https://hooks.slack.com/services/..." }`.

Posts one Slack message per new job via an [incoming webhook](https://api.slack.com/messaging/webhooks).
Create the webhook in your Slack workspace (Apps → Incoming Webhooks), then paste
the URL into the target config. Messages use mrkdwn with title, company,
location, and an Apply link. Digest mode sends one message listing all jobs.

## discord adapter

**Key:** `discord`. Config: `{ "webhook_url": "https://discord.com/api/webhooks/..." }`.

Posts one Discord message per new job via a [channel webhook](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks).
Create the webhook in your server (Server Settings → Integrations → Webhooks),
then paste the URL into the target config. Messages use a rich embed with title,
company, location, and a clickable apply link. Digest mode uses one embed with
a bullet list.

## telegram adapter

**Key:** `telegram`. Config: `{ "bot_token": "123456:ABC...", "chat_id": "123456789" }`.

Posts one Telegram message per new job via the [Bot API](https://core.telegram.org/bots/api).
Create a bot with [@BotFather](https://t.me/BotFather), send `/start` to it (or add it to a
group), then use your numeric chat id in config. Messages use HTML formatting with title,
company, location, and an Apply link. Digest mode sends one HTML message listing
all jobs.

## Adding a channel

See [../recipes.md](../recipes.md) → "add a new notification
channel". Test with mocked HTTP/transport; never send real notifications in
tests.
