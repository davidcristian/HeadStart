/** Feed of jobs discovered so far, filterable by search. */

import { useState } from "react";
import { api } from "../api";
import { Card, EmptyState, Field } from "../components/ui";
import { useAsync } from "../hooks/useAsync";

export function JobsPage() {
  const [searchId, setSearchId] = useState<number | "">("");
  const searches = useAsync(() => api.listSearches(), []);
  const jobs = useAsync(
    () => api.listJobs(searchId === "" ? undefined : Number(searchId)),
    [searchId],
  );

  return (
    <>
      <h1>Jobs</h1>
      <Card
        title="Discovered jobs"
        actions={
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
                <th>First seen</th>
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
                  <td className="muted">{new Date(j.first_seen_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
