# Module: Metrics

**Path:** `backend/app/core/metrics.py`

Prometheus metrics for scrape latency, pipeline outcomes, notification delivery,
and scheduler enqueue volume. Operators scrape these to answer "is the system
healthy?" without reading worker logs.

## Endpoints

| Process | URL | What it measures |
| ------- | --- | ---------------- |
| API (`uvicorn`) | `GET /metrics` | Synchronous "Run now" / source-test scrapes and any API-triggered pipeline runs |
| Worker (Celery) | `GET :METRICS_PORT/metrics` (default `9090`) | Scheduled pipeline runs, digest flushes, scheduler enqueue |

Scrape **both** targets in production — they run in separate processes and each
holds its own registry.

## Metrics

| Name | Type | Labels | Meaning |
| ---- | ---- | ------ | ------- |
| `jobnotifier_pipeline_runs_total` | Counter | `status` (`success`, `error`, `not_found`) | Completed pipeline runs |
| `jobnotifier_scrape_runs_total` | Counter | `adapter`, `status` (`success`, `error`) | Scrape attempts |
| `jobnotifier_scrape_duration_seconds` | Histogram | `adapter` | Time in `scraper.fetch` |
| `jobnotifier_scrape_jobs_found` | Histogram | `adapter` | Postings returned per scrape |
| `jobnotifier_notification_deliveries_total` | Counter | `notifier`, `status` (`sent`, `failed`), `mode` (`immediate`, `digest`) | Per-job delivery attempts |
| `jobnotifier_digest_flushes_total` | Counter | `status` (`success`, `error`) | Digest batch sends |
| `jobnotifier_scheduler_searches_enqueued_total` | Counter | — | Due searches enqueued per beat tick |

### Example PromQL

```promql
# Scrape success rate (5m window)
sum(rate(jobnotifier_scrape_runs_total{status="success"}[5m]))
/
sum(rate(jobnotifier_scrape_runs_total[5m]))

# Notification delivery failure rate
sum(rate(jobnotifier_notification_deliveries_total{status="failed"}[5m]))
/
sum(rate(jobnotifier_notification_deliveries_total[5m]))

# p95 scrape latency per adapter
histogram_quantile(0.95, sum by (adapter, le) (rate(jobnotifier_scrape_duration_seconds_bucket[5m])))
```

## Configuration

| Env var | Default | Purpose |
| ------- | ------- | ------- |
| `METRICS_ENABLED` | `true` | Set `false` to disable recording and hide `/metrics` |
| `METRICS_PORT` | `9090` | Worker-only HTTP port for `/metrics` |
| `METRICS_TOKEN` | *(empty)* | When set, `GET /metrics` requires `Authorization: Bearer <token>` |

Set `METRICS_TOKEN` in any deployment reachable from the internet.

## AWS / CloudWatch

On ECS, expose the worker metrics port on the task security group and scrape
with Prometheus, or use the [CloudWatch agent Prometheus
scraper](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-Prometheus-Scrape.html)
to forward the same exposition format. The API target group can add a path rule
for `/metrics` if you scrape the API process separately.

See [deployment.md](deployment.md) for service topology.
