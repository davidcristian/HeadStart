/** Responsive job list: table on desktop, cards on mobile. */

import { JobStatusBadge } from "./JobStatusBadge";
import { Button } from "./ui";
import { useMediaQuery } from "../hooks/useMediaQuery";
import { safeHref } from "../lib/safeHref";
import type { Job } from "../types";

type JobAction = "seen" | "applied" | "archived";

export function JobList({
  jobs,
  onStatusChange,
  canApply,
  onApply,
}: {
  jobs: Job[];
  onStatusChange: (jobId: number, status: JobAction) => void;
  canApply?: (job: Job) => boolean;
  onApply?: (job: Job) => void;
}) {
  const isMobile = useMediaQuery("(max-width: 900px)");

  if (isMobile) {
    return (
      <div className="job-cards">
        {jobs.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            onStatusChange={onStatusChange}
            canApply={canApply?.(job) ?? false}
            onApply={onApply}
          />
        ))}
      </div>
    );
  }

  return (
    <table className="table job-table">
      <thead>
        <tr>
          <th>Title</th>
          <th>Company</th>
          <th>Location</th>
          <th>Salary</th>
          <th>Status</th>
          <th>First seen</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {jobs.map((job) => (
          <JobTableRow
            key={job.id}
            job={job}
            onStatusChange={onStatusChange}
            canApply={canApply?.(job) ?? false}
            onApply={onApply}
          />
        ))}
      </tbody>
    </table>
  );
}

function JobTableRow({
  job,
  onStatusChange,
  canApply,
  onApply,
}: {
  job: Job;
  onStatusChange: (jobId: number, status: JobAction) => void;
  canApply: boolean;
  onApply?: (job: Job) => void;
}) {
  return (
    <tr>
      <td>
        <JobTitle job={job} />
        {job.summary && <div className="job-summary muted">{job.summary}</div>}
      </td>
      <td>{job.company || "-"}</td>
      <td>{job.location || "-"}</td>
      <td>{job.salary || "-"}</td>
      <td>
        <JobStatusBadge status={job.status} />
      </td>
      <td className="muted">{formatSeenAt(job.first_seen_at)}</td>
      <td>
        <JobActions
          job={job}
          onStatusChange={onStatusChange}
          canApply={canApply}
          onApply={onApply}
        />
      </td>
    </tr>
  );
}

function JobCard({
  job,
  onStatusChange,
  canApply,
  onApply,
}: {
  job: Job;
  onStatusChange: (jobId: number, status: JobAction) => void;
  canApply: boolean;
  onApply?: (job: Job) => void;
}) {
  return (
    <article className="job-card">
      <div className="job-card-header">
        <JobTitle job={job} />
        <JobStatusBadge status={job.status} />
      </div>
      <p className="job-card-meta">
        {[job.company, job.location].filter(Boolean).join(" · ") || "Unknown company"}
      </p>
      {job.summary && <p className="job-summary muted">{job.summary}</p>}
      {job.salary && <p className="job-card-salary muted">{job.salary}</p>}
      <p className="job-card-seen muted">First seen {formatSeenAt(job.first_seen_at)}</p>
      <JobActions job={job} onStatusChange={onStatusChange} canApply={canApply} onApply={onApply} />
    </article>
  );
}

function JobTitle({ job }: { job: Job }) {
  const href = safeHref(job.url);
  if (!href) return <span>{job.title}</span>;
  return (
    <a href={href} target="_blank" rel="noreferrer">
      {job.title}
    </a>
  );
}

function JobActions({
  job,
  onStatusChange,
  canApply,
  onApply,
}: {
  job: Job;
  onStatusChange: (jobId: number, status: JobAction) => void;
  canApply: boolean;
  onApply?: (job: Job) => void;
}) {
  return (
    <div className="row-actions job-actions">
      {canApply && onApply && <Button onClick={() => onApply(job)}>Apply</Button>}
      {job.status !== "seen" && job.status !== "closed" && (
        <Button variant="ghost" onClick={() => onStatusChange(job.id, "seen")}>
          Seen
        </Button>
      )}
      {job.status !== "applied" && (
        <Button variant="ghost" onClick={() => onStatusChange(job.id, "applied")}>
          Applied
        </Button>
      )}
      {job.status !== "archived" && (
        <Button variant="ghost" onClick={() => onStatusChange(job.id, "archived")}>
          Archive
        </Button>
      )}
    </div>
  );
}

function formatSeenAt(value: string): string {
  return new Date(value).toLocaleString();
}
