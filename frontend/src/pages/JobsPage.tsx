/** Feed of jobs discovered so far, filterable by search and triage status. */

import { useState } from "react";
import { api } from "../api";
import { JobStatusBadge } from "../components/JobStatusBadge";
import { Banner, Button, Card, EmptyState, Field } from "../components/ui";
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

function buildFeedUrl(baseUrl: string, searchId: number | "", status: "" | JobStatus): string {
  const url = new URL(baseUrl);
  if (searchId !== "") {
    url.searchParams.set("search_id", String(searchId));
  }
  if (status !== "") {
    url.searchParams.set("status", status);
  }
  return url.toString();
}

export function JobsPage() {
  const [searchId, setSearchId] = useState<number | "">("");
  const [status, setStatus] = useState<"" | JobStatus>("");
  const [feedMessage, setFeedMessage] = useState<string | null>(null);
  const searches = useAsync(() => api.listSearches(), []);
  const jobs = useAsync(
    () =>
      api.listJobs(
        searchId === "" ? undefined : Number(searchId),
        status === "" ? undefined : status,
      ),
    [searchId, status],
  );
  const feed = useAsync(() => api.getFeedUrl(), []);

  async function setJobStatus(jobId: number, next: "seen" | "applied" | "archived") {
    await api.updateJob(jobId, { status: next });
    jobs.reload();
  }

  async function copyFeedUrl() {
    if (!feed.data) return;
    const url = buildFeedUrl(feed.data.url, searchId, status);
    await navigator.clipboard.writeText(url);
    setFeedMessage("RSS feed URL copied to clipboard.");
  }

  async function rotateFeedUrl() {
    await api.rotateFeedUrl();
    feed.reload();
    setFeedMessage("RSS feed link regenerated. Update any feed readers using the old URL.");
  }

  const filteredFeedUrl = feed.data ? buildFeedUrl(feed.data.url, searchId, status) : "";

  return (
    <>
      <h1>Jobs</h1>
      <Card title="RSS feed">
        {feed.loading && <p>Loading feed URL...</p>}
        {feed.error && <Banner kind="error">Could not load RSS feed URL.</Banner>}
        {feed.data && (
          <>
            <p className="muted">
              Subscribe in any RSS reader. The URL respects the search and status filters selected
              below.
            </p>
            <Field label="Feed URL" hint="Anyone with this link can read your job feed.">
              <input readOnly value={filteredFeedUrl} onFocus={(e) => e.target.select()} />
            </Field>
            <div className="row-actions">
              <Button onClick={copyFeedUrl}>Copy feed URL</Button>
              <Button variant="ghost" onClick={rotateFeedUrl}>
                Regenerate link
              </Button>
            </div>
            {feedMessage && <p className="muted">{feedMessage}</p>}
          </>
        )}
      </Card>
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
                <th>Salary</th>
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
                  <td>{j.salary || "-"}</td>
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
