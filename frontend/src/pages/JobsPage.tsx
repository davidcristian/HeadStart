/** Feed of jobs discovered so far, filterable by search and triage status. */

import { useState } from "react";
import { api } from "../api";
import { JobStatusBadge } from "../components/JobStatusBadge";
import { Button, Card, EmptyState, Field } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import type { JobStatus } from "../types";

const STATUS_FILTERS: Array<{ value: "" | JobStatus; label: string }> = [
  { value: "", label: "All statuses" },
  { value: "new", label: "New" },
  { value: "seen", label: "Seen" },
  { value: "applied", label: "Applied" },
  { value: "archived", label: "Archived" },
  { value: "closed", label: "Closed" },
];

export function JobsPage() {
  const [searchId, setSearchId] = useState<number | "">("");
  const [status, setStatus] = useState<"" | JobStatus>("");
  const searches = useAsync(() => api.listSearches(), []);
  const jobs = useAsync(
    () =>
      api.listJobs(
        searchId === "" ? undefined : Number(searchId),
        status === "" ? undefined : status,
      ),
    [searchId, status],
  );

  async function setJobStatus(jobId: number, next: "seen" | "applied" | "archived") {
    await api.updateJob(jobId, { status: next });
    jobs.reload();
  }

  return (
    <>
      <h1>Jobs</h1>
      <Card
        title="Discovered jobs"
        actions={
          <div className="card-actions">
            <Field label="">
              <select value={status} onChange={(e) => setStatus(e.target.value as "" | JobStatus)}>
                {STATUS_FILTERS.map((option) => (
                  <option key={option.label} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="">
              <select
                value={searchId}
                onChange={(e) => setSearchId(e.target.value === "" ? "" : Number(e.target.value))}
              >
                <option value="">All searches</option>
                {searches.data?.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        }
      >
        {jobs.loading && <p>Loading...</p>}
        {jobs.data && jobs.data.length === 0 && (
          <EmptyState>No jobs seen yet. They appear here as searches run.</EmptyState>
        )}
        {jobs.data && jobs.data.length > 0 && (
          <table className="table">
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
              {jobs.data.map((j) => (
                <tr key={j.id}>
                  <td>
                    {j.url ? (
                      <a href={j.url} target="_blank" rel="noreferrer">
                        {j.title}
                      </a>
                    ) : (
                      j.title
                    )}
                  </td>
                  <td>{j.company || "-"}</td>
                  <td>{j.location || "-"}</td>
                  <td>
                    <JobStatusBadge status={j.status} />
                  </td>
                  <td className="muted">{new Date(j.first_seen_at).toLocaleString()}</td>
                  <td>
                    <div className="row-actions">
                      {j.status !== "seen" && j.status !== "closed" && (
                        <Button variant="ghost" onClick={() => setJobStatus(j.id, "seen")}>
                          Seen
                        </Button>
                      )}
                      {j.status !== "applied" && (
                        <Button variant="ghost" onClick={() => setJobStatus(j.id, "applied")}>
                          Applied
                        </Button>
                      )}
                      {j.status !== "archived" && (
                        <Button variant="ghost" onClick={() => setJobStatus(j.id, "archived")}>
                          Archive
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
