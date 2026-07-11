# Module: Summaries (AI match blurbs)

**Path:** `backend/app/summarizers/` (adapters) + `backend/app/services/summaries.py`
(orchestration)

Summaries add a short **"why this matches"** blurb to each new job. The pipeline
generates it after dedup/filtering and before notifying, then:

- attaches it to the `JobPosting` so every notifier can render it, and
- persists it on `seen_job.summary` so it shows in the Jobs feed / RSS and is
  reused for batched digests.

It is **best-effort and presentational**: a provider failure never blocks a
notification — the blurb is just left empty.

## Prompt injection hardening

LLM summarizer adapters share `app/summarizers/prompts.py`. Scraped
title/company/location are fenced in `<<<JOB_POSTING>>>` /
`<<<END_JOB_POSTING>>>` blocks; the system prompt treats that block as untrusted
data. `SummaryService.annotate` reuses `looks_like_prompt_injection` on those
fields and forces the offline `heuristic` provider when any posting in the batch
matches, so a poisoned board listing cannot steer the hosted model.

## Contract

```python
# app/summarizers/types.py
class SummaryContext(BaseModel):
    search_name: str | None = None
    filters: dict           # the search's filter JSON (keywords, location, ...)

# app/summarizers/base.py
class Summarizer(ABC):
    @abstractmethod
    def summarize(self, ctx: SummaryContext, jobs: list[JobPosting]) -> list[str]:
        """One blurb per posting, aligned with and same length as `jobs`."""
```

## Registry

Adapters self-register with `@register_summarizer("key")`, are imported in
`app/summarizers/adapters/__init__.py`, and are resolved with
`get_summarizer(key)` — the same pattern as scrapers/notifiers. Nothing branches
on the provider name; you add a file, not an `if`.

## Providers

| Key | When to use | Notes |
| --- | ----------- | ----- |
| `heuristic` | **Default.** Offline, free, deterministic | Builds the blurb from the search's own filters (matched keywords, workplace, location). No network or API key, so it is safe in CI/local/prod. Falls back to a neutral "New \<role\> at \<company\>" line when no filter matches. |
| `openai` | You want richer, natural-language blurbs in hosted/prod | Calls an OpenAI-compatible Chat Completions endpoint per job. Requires `OPENAI_API_KEY`; honors `OPENAI_MODEL` and `OPENAI_BASE_URL`. |
| `gemini` | You want hosted blurbs on Google AI instead of OpenAI | Calls the Gemini `generateContent` REST API per job. Requires `GEMINI_API_KEY`; honors `GEMINI_MODEL` and `GEMINI_BASE_URL`. |
| `anthropic` | You want hosted blurbs on Anthropic Claude instead of OpenAI/Gemini | Calls the Anthropic Messages REST API per job. Requires `ANTHROPIC_API_KEY`; honors `ANTHROPIC_MODEL`, `ANTHROPIC_BASE_URL`, and `ANTHROPIC_API_VERSION`. |
| `llamacpp` | **Local dev only.** Free summaries against a local model | Calls a llama.cpp `llama-server` OpenAI-compatible endpoint (default `http://localhost:8080/v1`). No API key required unless your server expects one. Start a server with `just llamacpp` (needs `LLAMACPP_MODEL_PATH`). The helper script passes sensible defaults (`--flash-attn on`, `--ctx-size 2048`, `--n-gpu-layers 99`); override via `LLAMACPP_FLASH_ATTN`, `LLAMACPP_CTX_SIZE`, `LLAMACPP_NGL`. Do not use in deployed environments — keep `SUMMARY_PROVIDER=openai` or `heuristic` there. |

## Per-user preferences (Pro)

Pro users can override the deployment-wide `SUMMARY_PROVIDER` and optionally store
their own API key for hosted providers (`openai`, `gemini`, `anthropic`). They can
also set **per-purpose** provider and model overrides for cover letters and future
inbox/resume agents — unset purposes inherit the global default, then env defaults.

| Endpoint | Purpose |
| -------- | ------- |
| `GET /summary-preferences` | Global + per-purpose selection, effective providers/models, and available options |
| `PATCH /summary-preferences` | Set global `provider` and optional `api_key`; patch `purpose_preferences` for `cover_letter`, `resume_curation`, `email_classify`, `email_draft` |

Keys are Fernet-encrypted at rest (`summary_api_key_ciphertext` on `user`). The key
belongs to the user's global `summary_provider` only: `resolve_ai_settings` attaches it
when the resolved purpose provider matches that global selection, and drops it otherwise
so a purpose override (e.g. `email_draft=gemini` while the stored key is OpenAI) cannot
send the secret to another vendor. Purpose overrides live in `ai_purpose_providers` /
`ai_purpose_models` JSON columns. The pipeline resolves per-user settings via
`resolve_summary_settings` (summaries) or `resolve_ai_settings(..., purpose)` (cover
letters and future agents). Non-Pro users may read preferences but receive `402` on
update (`feature_ai_summaries`). Settings UI: **Settings → AI models**.

## Configuration

All via env (see `.env.example` / `app/core/config.py`):

| Setting | Default | Meaning |
| ------- | ------- | ------- |
| `SUMMARIES_ENABLED` | `true` | Master switch; when off, blurbs are never generated |
| `SUMMARY_PROVIDER` | `heuristic` | Registered summarizer key (`heuristic`, `openai`, `gemini`, `anthropic`, or `llamacpp`) |
| `SUMMARY_MAX_CHARS` | `280` | Blurbs longer than this are truncated with `…` |
| `OPENAI_API_KEY` | _(empty)_ | Required for the `openai` provider |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model id |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Override for Azure OpenAI, OpenRouter, or other OpenAI-compatible gateways (use with `SUMMARY_PROVIDER=openai`) |
| `GEMINI_API_KEY` | _(empty)_ | Required for the `gemini` provider |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model id |
| `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta` | Override for proxies or alternate Google AI endpoints |
| `ANTHROPIC_API_KEY` | _(empty)_ | Required for the `anthropic` provider |
| `ANTHROPIC_MODEL` | `claude-3-5-haiku-latest` | Claude model id |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com/v1` | Override for proxies or alternate Anthropic endpoints |
| `ANTHROPIC_API_VERSION` | `2023-06-01` | Required `anthropic-version` header value for the Messages API |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | llama.cpp server base URL (`llamacpp` provider only) |
| `LLAMACPP_MODEL` | `local` | Model id sent in chat completion requests |
| `LLAMACPP_API_KEY` | _(empty)_ | Optional bearer token when the local server requires auth |

## Where the blurb appears

- **Notifications:** every channel (`ntfy`, `email`, `slack`, `discord`,
  `telegram`, `webhook`) renders the blurb when present, in both immediate and
  digest modes. The `webhook` JSON payload carries it as a `summary` field.
- **App:** the Jobs page shows it under each job title/card; the RSS feed
  prepends it to the item description.

## Adding a provider

See [../recipes.md](../recipes.md) → "add a summarizer provider".
Implement `Summarizer`, self-register, read any secrets from `settings`, and
**raise on failure** (the service swallows it). Test with mocked I/O under
`backend/tests/summarizers/`; never call a real model in tests.
