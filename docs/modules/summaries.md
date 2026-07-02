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
| `llamacpp` | **Local dev only.** Free summaries against a local model | Calls a llama.cpp `llama-server` OpenAI-compatible endpoint (default `http://localhost:8080/v1`). No API key required unless your server expects one. Start a server with `make llamacpp` (needs `LLAMACPP_MODEL_PATH`). The helper script passes sensible defaults (`--flash-attn on`, `--ctx-size 2048`, `--n-gpu-layers 99`); override via `LLAMACPP_FLASH_ATTN`, `LLAMACPP_CTX_SIZE`, `LLAMACPP_NGL`. Do not use in deployed environments — keep `SUMMARY_PROVIDER=openai` or `heuristic` there. |

## Per-user preferences (Pro)

Pro users can override the deployment-wide `SUMMARY_PROVIDER` and optionally store
their own API key for hosted providers (`openai`, `gemini`, `anthropic`).

| Endpoint | Purpose |
| -------- | ------- |
| `GET /summary-preferences` | Current selection, effective provider, and available options |
| `PATCH /summary-preferences` | Set `provider` (`heuristic` / `openai` / `gemini` / `anthropic`, or `null` for server default) and optional `api_key` (empty string clears a saved key) |

Keys are Fernet-encrypted at rest (`summary_api_key_ciphertext` on `user`). The
pipeline resolves per-user settings via `resolve_summary_settings` before calling
the summarizer registry. Non-Pro users may read preferences but receive `402` on
update (`feature_ai_summaries`). Settings UI: **Settings → AI summaries**.

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
