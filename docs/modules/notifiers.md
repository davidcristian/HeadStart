# Module: Notifiers

**Path:** `backend/app/notifiers/`

Notifiers deliver new jobs to a channel. Each channel is one self-registering
adapter. Built-in channels: `email` and `ntfy`.

## Contract

```python
# app/notifiers/types.py
class NotifyContext(BaseModel):
    target_type: str      # e.g. "ntfy"
    config: dict          # channel config from the NotificationTarget

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

## email adapter

**Key:** `email`. Config: `{ "to": "you@example.com" }`.

Uses the app-wide `SMTP_*` settings (same as password reset). Sends one
plain-text email per new job with subject `"<title> @ <company>"` and body
lines for company, location, and apply URL.

When SMTP is not configured, deliveries are recorded as `failed` with a clear
error (unlike password reset, which logs the link in dev).

## Adding a channel

See [../recipes.md](../recipes.md) → "add a new notification
channel". Test with mocked HTTP/transport; never send real notifications in
tests.
