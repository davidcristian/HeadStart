# 0011. Inbox automation stays dev-only

- **Status:** Accepted
- **Date:** 2026-07-03

## Context

Phase 20 adds application-pipeline automation: read recruiter email, classify
replies, draft follow-ups, and hand off interview scheduling. That requires
direct access to a user's mailbox (IMAP/SMTP credentials or OAuth tokens) and
eventually autonomous outbound email — sensitive capabilities that do not belong
on a hosted multi-tenant SaaS without explicit user-controlled infrastructure.

HeadStart already runs as both a self-hosted dev tool and a hosted product.

## Decision

1. Introduce an `inbox/` subsystem (registry + adapters) for mailbox I/O, starting
   with `imap_smtp`.
2. Store per-user mailbox credentials encrypted (`mailbox_credential` table).
3. Gate all inbox APIs and worker beat tasks behind `INBOX_AGENT_ENABLED`
   (default `false`). Document clearly that hosted operators should leave it off.
4. Optional `INBOX_USE_ENV_CREDENTIALS` + `INBOX_*` env vars for single-user local
   dev when no per-user credential is saved.
5. Ship classification, folder routing, ghost detection, reply drafting,
   response-delay auto-send, and beat orchestration **behind the same flag** —
   not as a hosted product feature.

## Shipped scope (Phase 20)

All of the following require `INBOX_AGENT_ENABLED=true` and stay off on hosted
multi-tenant production:

| Capability | Module / task |
| ---------- | ------------- |
| IMAP/SMTP mailbox connector | `inbox/adapters/imap_smtp.py` |
| Gmail OAuth connector | `inbox/adapters/gmail.py` |
| Email classification + thread linking | `email_classifiers/`; beat via `process_inbox_messages` |
| Folder / label routing | `InboxRoutingService`; IMAP MOVE or Gmail labels |
| Application-scoped inbox gate | `InboxGateService` (skips unrelated mail before LLM) |
| Ghost detection + self-archive | beat `detect_ghosted_applications` |
| Ghost recovery + interview handoff | `GhostRecoveryService`, `InterviewHandoffService` |
| Reply drafting + safe-send guardrails | `reply_drafters/`; `ReplySafeSendService` |
| Human-like auto-reply delay | `inbox_pending_reply`; beat `process_pending_replies` |
| Local LLM stack | `llamacpp` adapters for classify/draft/resume/cover-letter purposes |

Operator setup: [runbook.md → Local application agent](../runbook.md#local-application-agent-phase-20-dev-only).
Subsystem detail: [modules/inbox.md](../modules/inbox.md).

## Consequences

- Self-hosters can wire up IMAP/SMTP or Gmail OAuth locally without exposing
  mailbox access on production HeadStart Cloud.
- Services must call `InboxService.require_enabled()` before mailbox I/O.
- New inbox features reuse the same adapter contract, credential model, and flag.
- **Gmail OAuth** shipped in Phase 20c; **Outlook / Microsoft Graph** remains
  deferred (IMAP works for Outlook.com when the provider allows it).
- Autonomous email carries legal and misrepresentation risk; defaults keep
  `auto_reply_enabled` off and apply safe-send caps — see [modules/inbox.md](../modules/inbox.md).

## Alternatives considered

- **Hosted inbox with OAuth** — better UX but heavy compliance/tenancy work; not
  v1.
- **Reuse app-wide `SMTP_*` for inbound** — only covers outbound; no IMAP.
- **Store mailbox creds in `site_credential`** — wrong ownership model (mailbox
  is per user, not per job source).
