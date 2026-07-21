/** Small presentational UI primitives shared across pages. */

import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Button({
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" }) {
  return <button className={`btn btn-${variant}`} {...props} />;
}

export function Card({
  title,
  actions,
  children,
  className,
}: {
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={className ? `card ${className}` : "card"}>
      {(title || actions) && (
        <header className="card-header">
          {title && <h2>{title}</h2>}
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      <div className="card-body">{children}</div>
    </section>
  );
}

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

export function Badge({ on, labels }: { on: boolean; labels?: [string, string] }) {
  const [yes, no] = labels ?? ["enabled", "disabled"];
  return <span className={`badge ${on ? "badge-on" : "badge-off"}`}>{on ? yes : no}</span>;
}

export function Banner({
  kind,
  children,
}: {
  kind: "error" | "info" | "success";
  children: ReactNode;
}) {
  // Async error/success sinks (login, apply, settings, …) must announce to AT.
  const live =
    kind === "error"
      ? ({ role: "alert", "aria-live": "assertive" } as const)
      : ({ role: "status", "aria-live": "polite" } as const);
  return (
    <div className={`banner banner-${kind}`} {...live}>
      {children}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}
