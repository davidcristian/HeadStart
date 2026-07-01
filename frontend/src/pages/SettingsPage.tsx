/** Connection settings (API base URL), billing, account data controls, and ntfy help. */

import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Banner, Button, Card, Field } from "../components/ui";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import { getApiBaseUrl, setApiBaseUrl } from "../lib/settings";
import { planLabel } from "../lib/plan";
import type { BillingPeriod, BillingStatus } from "../types";

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
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [billingError, setBillingError] = useState<string>();
  const [billingBusy, setBillingBusy] = useState(false);
  const [billingPeriod, setBillingPeriod] = useState<BillingPeriod>("monthly");
  const billingNotice = searchParams.get("billing");

  useEffect(() => {
    let cancelled = false;
    async function loadBilling() {
      try {
        const status = await api.billingStatus();
        if (!cancelled) setBilling(status);
      } catch {
        if (!cancelled) setBilling(null);
      }
    }
    void loadBilling();
    return () => {
      cancelled = true;
    };
  }, [user?.plan]);

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

  async function startCheckout() {
    setBillingError(undefined);
    setBillingBusy(true);
    try {
      const { url } = await api.createCheckout(billingPeriod);
      window.location.assign(url);
    } catch (err) {
      setBillingError(err instanceof Error ? err.message : "Could not start checkout.");
      setBillingBusy(false);
    }
  }

  async function openPortal() {
    setBillingError(undefined);
    setBillingBusy(true);
    try {
      const { url } = await api.createBillingPortal();
      window.location.assign(url);
    } catch (err) {
      setBillingError(err instanceof Error ? err.message : "Could not open billing portal.");
      setBillingBusy(false);
    }
  }

  return (
    <>
      <h1>Settings</h1>

      {billingNotice === "success" && (
        <Banner kind="success">Subscription updated. Your plan may take a moment to refresh.</Banner>
      )}
      {billingNotice === "cancel" && (
        <Banner kind="info">Checkout was cancelled. No changes were made.</Banner>
      )}

      <Card title="Billing">
        {user && (
          <p>
            Current plan: <strong>{planLabel(user.plan)}</strong>
            {billing?.subscription_status ? (
              <>
                {" "}
                (subscription: <code>{billing.subscription_status}</code>)
              </>
            ) : null}
          </p>
        )}
        {billing?.configured ? (
          <>
            {billing.can_checkout ? (
              <>
                <p>Upgrade to Pro for more searches, digest mode, AI summaries, and premium scrapers.</p>
                <Field label="Billing period">
                  <select
                    value={billingPeriod}
                    onChange={(e) => setBillingPeriod(e.target.value as BillingPeriod)}
                    aria-label="Billing period"
                  >
                    <option value="monthly">Monthly</option>
                    <option value="annual">Annual (save ~17%)</option>
                  </select>
                </Field>
                <p>
                  <Button onClick={() => void startCheckout()} disabled={billingBusy}>
                    {billingBusy ? "Redirecting…" : "Upgrade to Pro"}
                  </Button>
                </p>
                {billing.trial_days > 0 ? (
                  <p className="muted">Includes a {billing.trial_days}-day free trial.</p>
                ) : null}
              </>
            ) : null}
            {billing.can_manage ? (
              <p>
                <Button variant="ghost" onClick={() => void openPortal()} disabled={billingBusy}>
                  {billingBusy ? "Opening…" : "Manage subscription"}
                </Button>
              </p>
            ) : null}
            {!billing.can_checkout && !billing.can_manage ? (
              <p>
                <a href="/pricing">View plans</a>
              </p>
            ) : null}
          </>
        ) : (
          <p>
            Paid checkout is not configured on this server.{" "}
            <a href="/pricing">View plans</a> or contact the operator to enable billing.
          </p>
        )}
        {billingError && <Banner kind="error">{billingError}</Banner>}
      </Card>

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

      <Card title="API connection">
        {saved && <Banner kind="success">Saved.</Banner>}
        <Field label="API base URL" hint="Where the backend is reachable from your browser.">
          <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
        </Field>
        <Button onClick={save}>Save</Button>
      </Card>

      <Card title="Receiving notifications">
        <p>
          HeadStart can deliver alerts via <strong>email</strong> (configure <code>SMTP_*</code> on
          the server), <strong>Slack</strong> or <strong>Discord</strong> (incoming webhooks),{" "}
          <strong>Telegram</strong> (Bot API), or <strong>ntfy</strong> push (no server mail setup
          required).
        </p>
        <h3>Email</h3>
        <ol className="help-list">
          <li>
            Set <code>SMTP_HOST</code>, <code>SMTP_FROM</code>, and related vars on the API server.
          </li>
          <li>
            Create an <strong>email</strong> target on the <strong>Notifications</strong> page with
            your address in <code>to</code>.
          </li>
          <li>
            Use &quot;Send test&quot; to confirm delivery, then attach the target to a search.
          </li>
        </ol>
        <h3>Slack</h3>
        <ol className="help-list">
          <li>
            In Slack, add an <strong>Incoming Webhooks</strong> app to your workspace and choose a
            channel.
          </li>
          <li>
            Create a <strong>slack</strong> target on the <strong>Notifications</strong> page and
            paste the webhook URL into <code>webhook_url</code>.
          </li>
          <li>
            Use &quot;Send test&quot; to confirm delivery, then attach the target to a search.
          </li>
        </ol>
        <h3>Discord</h3>
        <ol className="help-list">
          <li>
            In Discord, open your server&apos;s <strong>Integrations</strong> settings and create a{" "}
            <strong>Webhook</strong> for the channel you want alerts in.
          </li>
          <li>
            Create a <strong>discord</strong> target on the <strong>Notifications</strong> page and
            paste the webhook URL into <code>webhook_url</code>.
          </li>
          <li>
            Use &quot;Send test&quot; to confirm delivery, then attach the target to a search.
          </li>
        </ol>
        <h3>Telegram</h3>
        <ol className="help-list">
          <li>
            In Telegram, message <strong>@BotFather</strong>, run <code>/newbot</code>, and copy the
            bot token.
          </li>
          <li>
            Start a chat with your bot (or add it to a group) and note your numeric{" "}
            <code>chat_id</code>.
          </li>
          <li>
            Create a <strong>telegram</strong> target on the <strong>Notifications</strong> page
            with <code>bot_token</code> and <code>chat_id</code>.
          </li>
          <li>
            Use &quot;Send test&quot; to confirm delivery, then attach the target to a search.
          </li>
        </ol>
        <h3>ntfy push</h3>
        <ol className="help-list">
          <li>
            Install the <strong>ntfy</strong> app (iOS / Android) or open{" "}
            <a href="https://ntfy.sh" target="_blank" rel="noreferrer">
              ntfy.sh
            </a>
            .
          </li>
          <li>
            Create an <strong>ntfy</strong> target on the <strong>Notifications</strong> page with
            your chosen topic (pick something unguessable).
          </li>
          <li>Subscribe to that exact topic in the ntfy app.</li>
          <li>
            Use &quot;Send test&quot; to confirm delivery, then attach the target to a search.
          </li>
        </ol>
      </Card>
    </>
  );
}
