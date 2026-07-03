# 0011. Inbox automation stays dev-only

- **Status:** Accepted
- **Date:** 2026-07-03

## Context

Phase 20 adds application-pipeline automation: read recruiter email, classify
replies, draft follow-ups, and hand off interview scheduling. That requires
direct access to a user's mailbox (IMAP/SMTP credentials) and eventually
autonomous outbound email — sensitive capabilities that do not belong on a
hosted multi-tenant SaaS without explicit user-controlled infrastructure.

HeadStart already runs as both a self-hosted dev tool and a hosted product.

## Decision

1. Introduce an `inbox/` subsystem (registry + adapters) for mailbox I/O, starting
   with `imap_smtp`.
2. Store per-user mailbox credentials encrypted (`mailbox_credential` table).
3. Gate all inbox APIs and future worker tasks behind `INBOX_AGENT_ENABLED`
   (default `false`). Document clearly that hosted operators should leave it off.
4. Optional `INBOX_USE_ENV_CREDENTIALS` + `INBOX_*` env vars for single-user local
   dev when no per-user credential is saved.

Classification, folder routing, auto-reply, and beat orchestration remain
follow-up work; they also stay behind the same flag.

## Consequences

- Self-hosters can wire up IMAP/SMTP locally without exposing mailbox access on
  production HeadStart Cloud.
- Services must call `InboxService.require_enabled()` before mailbox I/O.
- Future inbox features reuse the same adapter contract and credential model.
- OAuth (Gmail/Outlook API) is deferred; IMAP is the v1 path.

## Alternatives considered

- **Hosted inbox with OAuth** — better UX but heavy compliance/tenancy work; not
  v1.
- **Reuse app-wide `SMTP_*` for inbound** — only covers outbound; no IMAP.
- **Store mailbox creds in `site_credential`** — wrong ownership model (mailbox
  is per user, not per job source).
