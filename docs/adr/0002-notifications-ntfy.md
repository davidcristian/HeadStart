# 0002. Notifications via ntfy

- **Status:** Accepted
- **Date:** 2026-06-28

## Context

The user wants notifications on iPhone, Android, web, and desktop with minimal
effort and no app-store overhead. Building native apps or wiring APNs/FCM
directly is large scope.

## Decision

Use [ntfy](https://ntfy.sh) as the notification channel. The worker POSTs to
`{server_url}/{topic}` with `Title`, `Priority`, `Tags`, and a `Click` header
(the job URL). The user subscribes to their topic in the ntfy app.

Default to the public `ntfy.sh`. A self-hosted ntfy server is available locally
via the Docker Compose `offline` profile and can be added on AWS later.

## Consequences

- Cross-platform push (iOS/Android/web/desktop) for near-zero effort.
- Notifier remains pluggable: ntfy is one adapter; email/web-push can be added
  later via the same registry (see [modules/notifiers.md](../modules/notifiers.md)).
- Public topics are world-readable if guessed; topics must be unguessable, and
  self-hosting with auth is the path for stronger privacy.

## Alternatives considered

- **Telegram bot:** great, but requires Telegram and bot setup.
- **Web Push (PWA):** no third party, but more plumbing (VAPID, service worker)
  and weaker iOS support.
- **Native apps:** maximum control, far too much scope for this project.
