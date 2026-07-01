import { Link } from "react-router-dom";
import { Button, Card, Field } from "../../components/ui";
import type { NotificationTarget } from "../../types";

type PortalsSubscribeCardProps = {
  targets: NotificationTarget[];
  targetId: number | "";
  setTargetId: (id: number | "") => void;
  interval: number;
  setInterval: (seconds: number) => void;
  onCreateAlerts: () => void;
  subscribePending: boolean;
};

export function PortalsSubscribeCard({
  targets,
  targetId,
  setTargetId,
  interval,
  setInterval,
  onCreateAlerts,
  subscribePending,
}: PortalsSubscribeCardProps) {
  return (
    <Card title="Subscribe to alerts">
      <p className="muted">
        Creates a source (if needed) and a scheduled search per selected company with your keyword
        filters.
      </p>
      <div className="form-grid">
        <Field label="Notification target">
          <select
            value={targetId}
            onChange={(e) => setTargetId(e.target.value === "" ? "" : Number(e.target.value))}
          >
            <option value="">Select target</option>
            {targets.map((target) => (
              <option key={target.id} value={target.id}>
                {target.name} ({target.type})
              </option>
            ))}
          </select>
        </Field>
        <Field label="Check interval (seconds)">
          <input
            type="number"
            min={60}
            value={interval}
            onChange={(e) => setInterval(Number(e.target.value))}
          />
        </Field>
      </div>
      {targets.length === 0 && (
        <p className="muted">
          <Link to="/app/targets">Create a notification target</Link> first.
        </p>
      )}
      <Button onClick={() => void onCreateAlerts()} disabled={subscribePending}>
        {subscribePending ? "Creating..." : "Create alerts"}
      </Button>
    </Card>
  );
}
