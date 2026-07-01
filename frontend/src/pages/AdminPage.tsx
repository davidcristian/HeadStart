/** Admin dashboard: user management and global scrape health. */

import { useState } from "react";
import { Badge, Banner, Button, Card, EmptyState } from "../components/ui";
import { AdminDataRequestsCard } from "../components/AdminDataRequestsCard";
import { AdminPromoCodesCard } from "../components/AdminPromoCodesCard";
import { useAdminStats, useAdminUsers, useMe } from "../hooks/queries";
import { useUpdateAdminUser } from "../hooks/mutations";
import type { AdminUser, PlanId } from "../types";

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat-tile">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

function UserRow({
  user,
  selfId,
  onUpdate,
}: {
  user: AdminUser;
  selfId: number;
  onUpdate: (
    id: number,
    patch: Partial<Pick<AdminUser, "is_active" | "is_admin" | "plan">>,
  ) => void;
}) {
  const isSelf = user.id === selfId;

  return (
    <tr>
      <td>{user.email}</td>
      <td>
        <Badge on={user.is_active} labels={["active", "inactive"]} />
      </td>
      <td>
        <Badge on={user.is_admin} labels={["admin", "member"]} />
      </td>
      <td>
        <select
          value={user.plan}
          disabled={isSelf}
          onChange={(e) => onUpdate(user.id, { plan: e.target.value as PlanId })}
          aria-label={`Plan for ${user.email}`}
        >
          <option value="free">Free</option>
          <option value="pro">Pro</option>
          <option value="team">Team</option>
        </select>
      </td>
      <td className="muted">{new Date(user.created_at).toLocaleDateString()}</td>
      <td className="row-actions">
        <Button
          variant="ghost"
          disabled={isSelf}
          onClick={() => onUpdate(user.id, { is_active: !user.is_active })}
        >
          {user.is_active ? "Deactivate" : "Activate"}
        </Button>
        <Button
          variant="ghost"
          disabled={isSelf}
          onClick={() => onUpdate(user.id, { is_admin: !user.is_admin })}
        >
          {user.is_admin ? "Remove admin" : "Make admin"}
        </Button>
      </td>
    </tr>
  );
}

export function AdminPage() {
  const users = useAdminUsers();
  const stats = useAdminStats();
  const me = useMe();
  const updateAdminUser = useUpdateAdminUser();
  const [error, setError] = useState<string>();

  async function updateUser(
    id: number,
    patch: Partial<Pick<AdminUser, "is_active" | "is_admin" | "plan">>,
  ) {
    setError(undefined);
    try {
      await updateAdminUser.mutateAsync({ id, patch });
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const s = stats.data;

  return (
    <>
      <h1>Admin</h1>
      {error && <Banner kind="error">{error}</Banner>}

      <Card title="System overview">
        {s ? (
          <div className="stat-grid">
            <StatTile label="Users" value={s.users_total} />
            <StatTile label="Active users" value={s.users_active} />
            <StatTile label="Searches" value={s.searches_total} />
            <StatTile label="Enabled searches" value={s.searches_enabled} />
            <StatTile label="Searches with errors" value={s.searches_with_error} />
            <StatTile label="Sources" value={s.sources_total} />
            <StatTile label="Seen jobs" value={s.seen_jobs_total} />
            <StatTile label="Deliveries sent" value={s.deliveries_sent} />
            <StatTile label="Delivery failures" value={s.deliveries_failed} />
          </div>
        ) : (
          <EmptyState>Loading stats...</EmptyState>
        )}
      </Card>

      <Card title="Recent scrape errors">
        {s && s.recent_errors.length === 0 ? (
          <EmptyState>No scrape errors recorded.</EmptyState>
        ) : (
          s && (
            <table className="table">
              <thead>
                <tr>
                  <th>Search</th>
                  <th>User</th>
                  <th>Last run</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {s.recent_errors.map((row) => (
                  <tr key={row.search_id}>
                    <td>{row.search_name}</td>
                    <td>{row.user_email}</td>
                    <td className="muted">
                      {row.last_run_at ? new Date(row.last_run_at).toLocaleString() : "-"}
                    </td>
                    <td className="error-text">{row.last_error}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </Card>

      <AdminPromoCodesCard />

      <AdminDataRequestsCard />

      <Card title="Users">
        <p className="muted">
          Change a member&apos;s plan here until Stripe billing is live. Admins are not capped by
          plan limits.
        </p>
        {users.data && users.data.length === 0 ? (
          <EmptyState>No users yet.</EmptyState>
        ) : (
          users.data && (
            <table className="table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Status</th>
                  <th>Role</th>
                  <th>Plan</th>
                  <th>Joined</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {users.data.map((user) => (
                  <UserRow
                    key={user.id}
                    user={user}
                    selfId={me.data?.id ?? -1}
                    onUpdate={updateUser}
                  />
                ))}
              </tbody>
            </table>
          )
        )}
      </Card>
    </>
  );
}
