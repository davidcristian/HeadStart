import { PORTAL_CATEGORY_LABELS } from "../../lib/portals";
import type { Portal } from "../../types";

type PortalSelectCardProps = {
  portal: Portal;
  checked: boolean;
  onToggle: () => void;
};

export function PortalSelectCard({ portal, checked, onToggle }: PortalSelectCardProps) {
  return (
    <li className={`portal-card portal-select-card ${checked ? "selected" : ""}`}>
      <label className="portal-select-label">
        <input type="checkbox" checked={checked} onChange={onToggle} />
        <span>
          <strong>{portal.company_name}</strong>
          <span className="portal-card-meta">
            <span className="portal-chip">{PORTAL_CATEGORY_LABELS[portal.category]}</span>
            {portal.already_added && (
              <span className="portal-chip portal-chip-muted">Source added</span>
            )}
          </span>
        </span>
      </label>
    </li>
  );
}
