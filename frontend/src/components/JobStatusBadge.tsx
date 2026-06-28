/** Job triage status badge for the jobs feed. */

import type { JobStatus } from "../types";

const LABELS: Record<JobStatus, string> = {
  new: "New",
  seen: "Seen",
  applied: "Applied",
  archived: "Archived",
  closed: "Closed",
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  return <span className={`badge badge-job badge-job-${status}`}>{LABELS[status]}</span>;
}
