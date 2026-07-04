/** Admin card listing recent GDPR export and deletion requests. */

import { Card, EmptyState } from "./ui";
import { useAdminDataRequests } from "../hooks/queries";
import type { DataRequestLog } from "../types";

function formatRequestType(type: DataRequestLog["request_type"]): string {
  return type === "export" ? "Data export" : "Account deletion";
}

export function AdminDataRequestsCard() {
  const requests = useAdminDataRequests();

  return (
    <Card title="GDPR data requests">
      <p className="muted">
        Audit trail of successful account data exports and deletions. Deletion rows show a
        one-way account pseudonym (not the plaintext email). Failed password attempts are not
        logged.
      </p>
      {requests.data && requests.data.length === 0 ? (
        <EmptyState>No export or deletion requests recorded yet.</EmptyState>
      ) : (
        requests.data && (
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Account</th>
                <th>Request</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {requests.data.map((row) => (
                <tr key={row.id}>
                  <td className="muted">{new Date(row.created_at).toLocaleString()}</td>
                  <td>{row.user_email}</td>
                  <td>{formatRequestType(row.request_type)}</td>
                  <td className="muted">{row.ip_address ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}
    </Card>
  );
}
