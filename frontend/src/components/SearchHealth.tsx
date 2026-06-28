/** Scrape and delivery health indicators for a search row. */

import { formatDateTime, formatRelativeTime } from "../lib/format";
import type { Search } from "../types";

function healthKind(search: Search): "ok" | "error" | "warn" | "unknown" {
  if (search.last_error) return "error";
  if (search.recent_delivery_failures.length > 0) return "warn";
  if (search.last_run_at) return "ok";
  return "unknown";
}

const LABELS: Record<ReturnType<typeof healthKind>, string> = {
  ok: "healthy",
  error: "scrape error",
  warn: "delivery issues",
  unknown: "not run yet",
};

export function SearchLastRun({ at }: { at: string | null }) {
  if (!at) return <span className="muted">Never</span>;
  return (
    <span className="muted" title={formatDateTime(at)}>
      {formatRelativeTime(at)}
    </span>
  );
}

export function SearchHealthBadge({ search }: { search: Search }) {
  const kind = healthKind(search);
  return <span className={`badge badge-health badge-health-${kind}`}>{LABELS[kind]}</span>;
}

export function SearchHealthDetails({ search }: { search: Search }) {
  const hasScrapeError = Boolean(search.last_error);
  const hasDeliveryFailures = search.recent_delivery_failures.length > 0;
  if (!hasScrapeError && !hasDeliveryFailures) return null;

  return (
    <div className="health-details">
      {hasScrapeError && (
        <p className="health-line health-line-error" title={search.last_error ?? undefined}>
          <strong>Scrape:</strong> {search.last_error}
        </p>
      )}
      {hasDeliveryFailures && (
        <div className="health-line health-line-warn">
          <strong>
            Delivery failures ({search.recent_delivery_failures.length}
            {search.recent_delivery_failures.length >= 5 ? "+" : ""}):
          </strong>
          <ul className="health-failures">
            {search.recent_delivery_failures.map((failure) => (
              <li key={`${failure.sent_at}-${failure.job_title}`}>
                <a href={failure.job_url} target="_blank" rel="noreferrer">
                  {failure.job_title}
                </a>
                {failure.error ? ` — ${failure.error}` : ""}
                <span className="muted"> ({formatRelativeTime(failure.sent_at)})</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
