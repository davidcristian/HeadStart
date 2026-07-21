# Module: Metrics

**Path:** `backend/app/core/metrics.py`

Prometheus metrics for scrape latency, pipeline outcomes, notification delivery,
and scheduler enqueue volume. Operators scrape these to answer "is the system
healthy?" without reading worker logs.

## Endpoints

| Process | URL | What it measures |
| ------- | --- | ---------------- |
| API (`uvicorn`) | `GET /metrics` | Source-test scrapes and other API-side work (manual Run now is queued on the worker) |
| Worker (Celery) | `GET :METRICS_PORT/metrics` (default `9090`) | Scheduled + manual pipeline runs, digest flushes, scheduler enqueue |

Scrape **both** targets in production, because they run in separate processes
and each holds its own registry. When `METRICS_TOKEN` is set, **both** endpoints require
`Authorization: Bearer <token>` (API route and worker WSGI server).

### Prefork worker port binding

Celery's default prefork pool runs `worker_process_init` in every child. Each
child calls `start_metrics_server(METRICS_PORT)`. The first child to bind wins;
later children catch `EADDRINUSE`, log a warning, and continue so the pool does
not crash-loop. Prometheus therefore scrapes **one** child's in-process registry
per worker OS process (not an aggregate across concurrency slots).

## Metrics

| Name | Type | Labels | Meaning |
| ---- | ---- | ------ | ------- |
| `headstart_pipeline_runs_total` | Counter | `status` (`success`, `error`, `not_found`) | Completed pipeline runs |
| `headstart_scrape_runs_total` | Counter | `adapter`, `status` (`success`, `error`) | Scrape attempts |
| `headstart_scrape_duration_seconds` | Histogram | `adapter` | Time in `scraper.fetch` |
| `headstart_scrape_jobs_found` | Histogram | `adapter` | Postings returned per scrape |
| `headstart_notification_deliveries_total` | Counter | `notifier`, `status` (`sent`, `failed`), `mode` (`immediate`, `digest`) | Per-job delivery attempts |
| `headstart_digest_flushes_total` | Counter | `status` (`success`, `error`) | Digest batch sends |
| `headstart_scheduler_searches_enqueued_total` | Counter | *(none)* | Due searches enqueued per beat tick |
| `headstart_auth_login_failures_total` | Counter | *(none)* | Failed login attempts |

### Example PromQL

```promql
# Scrape success rate (5m window)
sum(rate(headstart_scrape_runs_total{status="success"}[5m]))
/
sum(rate(headstart_scrape_runs_total[5m]))

# Notification delivery failure rate
sum(rate(headstart_notification_deliveries_total{status="failed"}[5m]))
/
sum(rate(headstart_notification_deliveries_total[5m]))

# Failed logins (credential stuffing signal)
sum(rate(headstart_auth_login_failures_total[5m]))

# p95 scrape latency per adapter
histogram_quantile(0.95, sum by (adapter, le) (rate(headstart_scrape_duration_seconds_bucket[5m])))
```

## Configuration

| Env var | Default | Purpose |
| ------- | ------- | ------- |
| `METRICS_ENABLED` | `true` | Set `false` to disable recording and hide `/metrics` |
| `METRICS_PORT` | `9090` | Worker-only HTTP port for `/metrics` |
| `METRICS_TOKEN` | *(empty)* | When set, API and worker `/metrics` require `Authorization: Bearer <token>` |

Set `METRICS_TOKEN` in any deployment reachable from the internet (or any network
that can reach the worker metrics port). Empty token keeps both surfaces open for
local scrapes; AWS ECS always injects a generated token from Secrets Manager.
Retrieve it with `aws secretsmanager get-secret-value` for Prometheus
`Authorization: Bearer` scrapes.

## AWS / CloudWatch

On ECS, expose the worker metrics port on the task security group and scrape
with Prometheus, or use the [CloudWatch agent Prometheus
scraper](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-Prometheus-Scrape.html)
to forward the same exposition format. The API target group can add a path rule
for `/metrics` if you scrape the API process separately.

See [deployment.md](deployment.md) for service topology.
