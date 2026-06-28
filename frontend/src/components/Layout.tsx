/** App shell: sidebar navigation + routed content. */

import { NavLink, Outlet } from "react-router-dom";
import { useAsync } from "../hooks/useAsync";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import { Button } from "./ui";

const NAV = [
  { to: "/searches", label: "Searches" },
  { to: "/jobs", label: "Jobs" },
  { to: "/sources", label: "Sources" },
  { to: "/targets", label: "Notifications" },
  { to: "/credentials", label: "Site credentials" },
  { to: "/settings", label: "Settings" },
];

export function Layout() {
  const health = useAsync(() => api.health(), []);
  const { user, logout } = useAuth();

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">JN</span>
          <span className="brand-name">JobNotifier</span>
        </div>
        <nav>
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          {user && (
            <div className="user-box">
              <span className="user-email" title={user.email}>
                {user.email}
                {user.is_admin ? " (admin)" : ""}
              </span>
              <Button variant="ghost" onClick={logout}>
                Sign out
              </Button>
            </div>
          )}
          {health.data ? (
            <span className="status-ok">
              API v{health.data.version} - {health.data.environment}
            </span>
          ) : (
            <span className="status-bad">API unreachable</span>
          )}
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
