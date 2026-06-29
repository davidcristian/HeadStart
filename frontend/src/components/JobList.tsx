/** Responsive job list: table on desktop, cards on mobile. */

import { JobStatusBadge } from "./JobStatusBadge";
import { Button } from "./ui";
import { useMediaQuery } from "../hooks/useMediaQuery";
import type { Job } from "../types";

type JobAction = "seen" | "applied" | "archived";

export function JobList({
  jobs,
  onStatusChange,
}: {
  jobs: Job[];
  onStatusChange: (jobId: number, status: JobAction) => void;
}) {
  const isMobile = useMediaQuery("(max-width: 900px)");

  if (isMobile) {
    return (
      <div className="job-cards">
        {jobs.map((job) => (
          <JobCard key={job.id} job={job} onStatusChange={onStatusChange} />
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
            <th>Status</th>
            <th>First seen</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <JobTableRow key={job.id} job={job} onStatusChange={onStatusChange} />
          ))}
        </tbody>
      </table>
  );
}

function JobTableRow({
  job,
  onStatusChange,
}: {
  job: Job;
  onStatusChange: (jobId: number, status: JobAction) => void;
}) {
  return (
    <tr>
      <td>
        <JobTitle job={job} />
      </td>
      <td>{job.company || "-"}</td>
      <td>{job.location || "-"}</td>
      <td>
        <JobStatusBadge status={job.status} />
      </td>
      <td className="muted">{formatSeenAt(job.first_seen_at)}</td>
      <td>
        <JobActions job={job} onStatusChange={onStatusChange} />
      </td>
    </tr>
  );
}

function JobCard({
  job,
  onStatusChange,
}: {
  job: Job;
  onStatusChange: (jobId: number, status: JobAction) => void;
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
      <p className="job-card-seen muted">First seen {formatSeenAt(job.first_seen_at)}</p>
      <JobActions job={job} onStatusChange={onStatusChange} />
    </article>
  );
}

function JobTitle({ job }: { job: Job }) {
  if (!job.url) return <span>{job.title}</span>;
  return (
    <a href={job.url} target="_blank" rel="noreferrer">
      {job.title}
    </a>
  );
}

function JobActions({
  job,
  onStatusChange,
}: {
  job: Job;
  onStatusChange: (jobId: number, status: JobAction) => void;
}) {
  return (
    <div className="row-actions job-actions">
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
