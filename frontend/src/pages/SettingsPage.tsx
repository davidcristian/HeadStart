/** Connection settings (API base URL), billing, account data controls, and ntfy help. */

import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { NotificationHelpCard } from "../components/settings/NotificationHelpCard";
import { SettingsBillingCard } from "../components/settings/SettingsBillingCard";
import { Banner, Button, Card, Field } from "../components/ui";
import { useCookieConsent } from "../components/CookieConsentContext";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import { getApiBaseUrl, setApiBaseUrl } from "../lib/settings";
import { planLabel } from "../lib/plan";

export function SettingsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { logout, user, refreshUser } = useAuth();
  const [baseUrl, setBaseUrl] = useState(getApiBaseUrl());
  const [saved, setSaved] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string>();
  const [deletePassword, setDeletePassword] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string>();
  const billingNotice = searchParams.get("billing");
  const { choice, openCookieSettings } = useCookieConsent();

  useEffect(() => {
    if (billingNotice === "success") {
      void refreshUser();
      const next = new URLSearchParams(searchParams);
      next.delete("billing");
      setSearchParams(next, { replace: true });
    }
  }, [billingNotice, refreshUser, searchParams, setSearchParams]);

  function save() {
    setApiBaseUrl(baseUrl);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  async function exportData() {
    setExportError(undefined);
    setExporting(true);
    try {
      const data = await api.exportMyData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const stamp = data.exported_at.slice(0, 10);
      anchor.href = url;
      anchor.download = `headstart-export-${stamp}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setExporting(false);
    }
  }

  async function deleteAccount() {
    setDeleteError(undefined);
    if (!deletePassword) {
      setDeleteError("Enter your password to confirm deletion.");
      return;
    }
    setDeleting(true);
    try {
      await api.deleteAccount(deletePassword);
      logout();
      navigate("/");
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Could not delete account.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      <h1>Settings</h1>

      {billingNotice === "success" && (
        <Banner kind="success">
          Subscription updated. Your plan may take a moment to refresh.
        </Banner>
      )}
      {billingNotice === "cancel" && (
        <Banner kind="info">Checkout was cancelled. No changes were made.</Banner>
      )}

      {user ? <SettingsBillingCard userPlan={user.plan} /> : null}

      <Card title="Your account">
        {user && (
          <p>
            Signed in as <strong>{user.email}</strong> on the{" "}
            <strong>{planLabel(user.plan)}</strong> plan.
            {user.is_admin ? " Admin accounts are not capped by plan limits." : null}{" "}
            <a href="/pricing">View plans</a>
          </p>
        )}
        <p>
          Download a JSON copy of your sources, searches, notification targets, credentials,
          application profile, and job history. Deleting your account permanently removes all of
          that data.
        </p>
        {exportError && <Banner kind="error">{exportError}</Banner>}
        <p>
          <Button onClick={() => void exportData()} disabled={exporting}>
            {exporting ? "Preparing export…" : "Export my data"}
          </Button>
        </p>
        {deleteError && <Banner kind="error">{deleteError}</Banner>}
        <Field
          label="Delete account"
          hint="This cannot be undone. Enter your password to confirm permanent deletion."
        >
          <input
            type="password"
            autoComplete="current-password"
            aria-label="Confirm account deletion password"
            value={deletePassword}
            onChange={(e) => setDeletePassword(e.target.value)}
          />
        </Field>
        <Button variant="danger" onClick={() => void deleteAccount()} disabled={deleting}>
          {deleting ? "Deleting…" : "Delete my account"}
        </Button>
      </Card>

      <Card title="Privacy & cookies">
        <p>
          Cookie consent:{" "}
          <strong>
            {choice === "all"
              ? "Accept all (optional cookies allowed when enabled)"
              : choice === "essential"
                ? "Essential only"
                : "Not set"}
          </strong>
          . Essential cookies keep you signed in; optional cookies are not loaded today.
        </p>
        <Button type="button" variant="ghost" onClick={openCookieSettings}>
          Cookie settings
        </Button>
      </Card>

      <Card title="API connection">
        {saved && <Banner kind="success">Saved.</Banner>}
        <Field label="API base URL" hint="Where the backend is reachable from your browser.">
          <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
        </Field>
        <Button onClick={save}>Save</Button>
      </Card>

      <Card title="Receiving notifications">
        <NotificationHelpCard />
      </Card>
    </>
  );
}
