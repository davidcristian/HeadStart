# 0008. Encrypted per-user application profile for auto-apply

- **Status:** Accepted
- **Date:** 2026-06-29

## Context

[Auto-apply](../roadmap.md) lets users submit applications from
HeadStart instead of only opening apply links. Every apply flow needs the same
structured candidate data: contact details, links, a resume, a cover-letter
template, and answers to recurring questions (work authorization, notice period,
etc.). That data is PII and must be stored safely. Unlike a session cookie, the
user needs to read and edit it. This is the foundational, storage-only slice of
auto-apply; apply adapters and orchestration come later.

## Decision

- Add an `application_profile` entity owned by a `user` (singleton: `unique` on
  `user_id`). It stores one JSON payload (`full_name`, `email`, `phone`,
  `location`, `links`, `resume_text`, `cover_letter_template`, `answers`) that is
  **Fernet-encrypted at rest** (`app.core.crypto`); only `data_ciphertext` is
  persisted. The Fernet key is the existing `CREDENTIALS_SECRET_KEY` (no new
  secret).
- **Return the decrypted profile to its owner.** This differs deliberately from
  [ADR-0005](0005-encrypted-site-credentials.md), where credential secrets are
  write-only. A profile is the user's own editable data, so a write-only model
  would make the UI unusable.
- Expose a singleton REST shape: `GET` (empty defaults with `exists=false` when
  unset), `PUT` (full replacement), `DELETE` (clear). All routes are scoped to
  the authenticated user.
- **Scope now: storage + retrieval only.** Apply adapters, the orchestration
  service, the Jobs "Apply" action, and per-source consent are deferred.

## Consequences

- Reuses the existing crypto module and secret; rotating `CREDENTIALS_SECRET_KEY`
  makes saved profiles unreadable, so the user re-enters them (the same
  trade-off as credentials).
- Profiles follow the same per-user isolation as everything else (ADR-0004).
- Provides a stable seam: apply adapters can read a decrypted `ProfileData`
  without re-deriving the storage/encryption concern.

## Alternatives considered

- **Store profile fields as plaintext columns/JSON.** Simplest, but leaves PII
  unencrypted at rest; rejected.
- **Reuse `site_credential` for profile data.** Conflates a write-only secret
  with editable user data and is keyed per `(user, source)` rather than per
  user; rejected.
- **Multiple named profiles per user.** Useful later (e.g. tailored resumes per
  role), but adds CRUD surface the first auto-apply slice does not need. Start
  with a singleton; revisit if demand appears.
