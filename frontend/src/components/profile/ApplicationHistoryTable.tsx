/** Application history audit log for the profile page. */

import { EmptyState } from "../ui";
import type { ApplicationLog } from "../../types";

interface ApplicationHistoryCardProps {
  entries: ApplicationLog[] | undefined;
  isPending: boolean;
}

export function ApplicationHistoryTable({ entries, isPending }: ApplicationHistoryCardProps) {
  if (isPending) return <p>Loading...</p>;
  if (!entries || entries.length === 0) {
    return <EmptyState>No application attempts yet.</EmptyState>;
  }

  return (
    <table className="table">
      <thead>
        <tr>
          <th>When</th>
          <th>Job</th>
          <th>Result</th>
          <th>Details</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => (
          <tr key={entry.id}>
            <td className="muted">{new Date(entry.created_at).toLocaleString()}</td>
            <td>
              <strong>{entry.job_title}</strong>
              <div className="muted">{entry.job_company}</div>
            </td>
            <td>
              {entry.dry_run ? "Preview" : entry.status}
              {entry.error && <div className="muted">{entry.error}</div>}
            </td>
            <td>
              {entry.external_application_id && (
                <div className="muted">ID: {entry.external_application_id}</div>
              )}
              {entry.job_url && (
                <a href={entry.job_url} target="_blank" rel="noreferrer">
                  View posting
                </a>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
