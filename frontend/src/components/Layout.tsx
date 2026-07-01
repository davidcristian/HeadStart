/** App shell: sidebar on desktop, bottom nav on mobile. */

import { useCallback, useRef, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { FreeTierAd } from "./FreeTierAd";
import { useHealth } from "../hooks/queries";
import { useFocusTrap } from "../hooks/useFocusTrap";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import { Brand } from "./Brand";
import { Button } from "./ui";

const PRIMARY_NAV = [
  { to: "/app/jobs", label: "Jobs" },
  { to: "/app/searches", label: "Searches" },
  { to: "/app/sources", label: "Sources" },
];

const MORE_NAV = [
  { to: "/app/targets", label: "Notifications" },
  { to: "/app/credentials", label: "Site credentials" },
  { to: "/app/profile", label: "Application profile" },
  { to: "/app/settings", label: "Settings" },
];

const DESKTOP_NAV = [
  { to: "/app/searches", label: "Searches" },
  { to: "/app/jobs", label: "Jobs" },
  { to: "/app/sources", label: "Sources" },
  { to: "/app/targets", label: "Notifications" },
  { to: "/app/credentials", label: "Site credentials" },
  { to: "/app/profile", label: "Application profile" },
  { to: "/app/settings", label: "Settings" },
];

const ADMIN_NAV = { to: "/app/admin", label: "Admin" };

export function Layout() {
  const health = useHealth();
  const { user, logout } = useAuth();
  const [moreOpen, setMoreOpen] = useState(false);
  const moreSheetRef = useRef<HTMLDivElement>(null);
  const closeMore = useCallback(() => setMoreOpen(false), []);

  useFocusTrap(moreOpen, moreSheetRef, closeMore);

  return (
    <div className="layout">
      <aside className="sidebar">
        <Brand to="/app/jobs" />
        <nav>
          {DESKTOP_NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
          {user?.is_admin && (
            <NavLink
              to={ADMIN_NAV.to}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            >
              {ADMIN_NAV.label}
            </NavLink>
          )}
        </nav>
        <FreeTierAd variant="sidebar" />
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

      <div className="app-main">
        <main className="content">
          <Outlet />
        </main>

        <FreeTierAd variant="mobile" />

        <nav className="mobile-nav" aria-label="Primary">
          {PRIMARY_NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `mobile-nav-link ${isActive ? "active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
          <button
            type="button"
            className={`mobile-nav-link mobile-nav-more ${moreOpen ? "active" : ""}`}
            aria-expanded={moreOpen}
            onClick={() => setMoreOpen((open) => !open)}
          >
            More
          </button>
        </nav>

        {moreOpen && (
          <div className="mobile-more-backdrop" onClick={closeMore}>
            <div
              className="mobile-more-sheet"
              ref={moreSheetRef}
              role="dialog"
              aria-modal="true"
              aria-label="More navigation"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="mobile-more-header">
                <span className="brand-name">More</span>
                <Button variant="ghost" onClick={closeMore}>
                  Close
                </Button>
              </div>
              <nav className="mobile-more-links">
                {MORE_NAV.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
                    onClick={closeMore}
                  >
                    {item.label}
                  </NavLink>
                ))}
                {user?.is_admin && (
                  <NavLink
                    to={ADMIN_NAV.to}
                    className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
                    onClick={closeMore}
                  >
                    {ADMIN_NAV.label}
                  </NavLink>
                )}
              </nav>
              {user && (
                <div className="mobile-more-footer">
                  <span className="user-email" title={user.email}>
                    {user.email}
                  </span>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      closeMore();
                      logout();
                    }}
                  >
                    Sign out
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
