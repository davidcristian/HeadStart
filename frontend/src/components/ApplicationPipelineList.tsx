/** Application pipeline cards with expandable attempt timeline. */

import { useState } from "react";
import { ApplicationStageBadge } from "./ApplicationStageBadge";
import { Button } from "./ui";
import { useMediaQuery } from "../hooks/useMediaQuery";
import type { ApplicationPipelineItem } from "../types";

const ATTEMPT_LABELS: Record<string, string> = {
  queued: "Queued",
  processing: "Processing",
  submitted: "Submitted",
  failed: "Failed",
};

export function ApplicationPipelineList({ items }: { items: ApplicationPipelineItem[] }) {
  const isMobile = useMediaQuery("(max-width: 900px)");

  if (isMobile) {
    return (
      <div className="application-cards">
        {items.map((item) => (
          <ApplicationPipelineCard key={item.job_id} item={item} />
        ))}
      </div>
    );
  }

  return (
    <table className="table application-table">
      <thead>
        <tr>
          <th>Job</th>
          <th>Stage</th>
          <th>Applied</th>
          <th>Latest attempt</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <ApplicationPipelineRow key={item.job_id} item={item} />
        ))}
      </tbody>
    </table>
  );
}

function ApplicationPipelineRow({ item }: { item: ApplicationPipelineItem }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <tr>
        <td>
          <JobSummary item={item} />
          {item.company && <div className="muted">{item.company}</div>}
        </td>
        <td>
          <ApplicationStageBadge stage={item.pipeline_stage} />
        </td>
        <td className="muted">{formatAppliedAt(item.applied_at)}</td>
        <td className="muted">{formatLatestAttempt(item)}</td>
        <td>
          {item.attempts.length > 0 && (
            <Button variant="ghost" onClick={() => setOpen((value) => !value)}>
              {open ? "Hide timeline" : "Timeline"}
            </Button>
          )}
        </td>
      </tr>
      {open && item.attempts.length > 0 && (
        <tr className="application-timeline-row">
          <td colSpan={5}>
            <AttemptTimeline attempts={item.attempts} />
          </td>
        </tr>
      )}
    </>
  );
}

function ApplicationPipelineCard({ item }: { item: ApplicationPipelineItem }) {
  const [open, setOpen] = useState(false);

  return (
    <article className="application-card">
      <div className="application-card-header">
        <JobSummary item={item} />
        <ApplicationStageBadge stage={item.pipeline_stage} />
      </div>
      <p className="application-card-meta muted">
        {[item.company, item.location].filter(Boolean).join(" · ") || "Unknown company"}
      </p>
      <p className="application-card-applied muted">Applied {formatAppliedAt(item.applied_at)}</p>
      <p className="application-card-latest muted">{formatLatestAttempt(item)}</p>
      {item.attempts.length > 0 && (
        <>
          <Button variant="ghost" onClick={() => setOpen((value) => !value)}>
            {open ? "Hide timeline" : "Show timeline"}
          </Button>
          {open && <AttemptTimeline attempts={item.attempts} />}
        </>
      )}
    </article>
  );
}

function JobSummary({ item }: { item: ApplicationPipelineItem }) {
  if (!item.url) return <strong>{item.title}</strong>;
  return (
    <a href={item.url} target="_blank" rel="noreferrer">
      <strong>{item.title}</strong>
    </a>
  );
}

function AttemptTimeline({ attempts }: { attempts: ApplicationPipelineItem["attempts"] }) {
  return (
    <ol className="application-timeline">
      {attempts.map((attempt) => (
        <li key={attempt.id} className="application-timeline-item">
          <span className="application-timeline-time muted">
            {new Date(attempt.created_at).toLocaleString()}
          </span>
          <span className="application-timeline-status">
            {ATTEMPT_LABELS[attempt.status] ?? attempt.status}
          </span>
          {attempt.external_application_id && (
            <span className="muted">ID: {attempt.external_application_id}</span>
          )}
          {attempt.error && <span className="application-timeline-error">{attempt.error}</span>}
        </li>
      ))}
    </ol>
  );
}

function formatAppliedAt(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function formatLatestAttempt(item: ApplicationPipelineItem): string {
  const latest = item.latest_attempt;
  if (!latest) return "No live attempts yet";
  const label = ATTEMPT_LABELS[latest.status] ?? latest.status;
  if (latest.error) return `${label}: ${latest.error}`;
  return label;
}
