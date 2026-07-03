/** Dev-only inbox mailbox settings (IMAP/SMTP, Gmail OAuth, Outlook OAuth, or Yahoo OAuth). */

import { useEffect, useState } from "react";
import { Banner, Button, Card, Field } from "../ui";
import { api } from "../../api";
import type { MailboxConfig, MailboxCredential } from "../../types";

const EMPTY_IMAP_CONFIG: MailboxConfig = {
  imap_host: "imap.gmail.com",
  imap_user: "",
  imap_password: "",
  smtp_host: "smtp.gmail.com",
  smtp_password: "",
  smtp_from: "",
};

type SettingsInboxCardProps = {
  mailboxNotice?: string | null;
};

export function SettingsInboxCard({ mailboxNotice }: SettingsInboxCardProps) {
  const [credential, setCredential] = useState<MailboxCredential | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [imapConfig, setImapConfig] = useState<MailboxConfig>(EMPTY_IMAP_CONFIG);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(undefined);
      try {
        const row = await api.getMailboxCredentials();
        if (!cancelled) {
          setCredential(row);
          if (row.connector_type === "imap_smtp") {
            setImapConfig((current) => ({
              ...current,
              imap_host: row.imap_host ?? current.imap_host,
              smtp_host: row.smtp_host ?? current.smtp_host,
              imap_user: row.imap_user ?? current.imap_user,
              smtp_from: row.imap_user ?? current.smtp_from,
            }));
          }
        }
      } catch (err) {
        if (!cancelled) {
          setCredential(null);
          if (!(err instanceof Error) || !err.message.toLowerCase().includes("not configured")) {
            setError(err instanceof Error ? err.message : "Could not load mailbox settings.");
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [mailboxNotice]);

  useEffect(() => {
    if (mailboxNotice === "gmail_connected") {
      setNotice("Gmail connected successfully.");
    } else if (mailboxNotice === "gmail_error") {
      setError("Gmail connection failed. Try again or use IMAP credentials.");
    } else if (mailboxNotice === "outlook_connected") {
      setNotice("Outlook connected successfully.");
    } else if (mailboxNotice === "outlook_error") {
      setError("Outlook connection failed. Try again or use IMAP credentials.");
    } else if (mailboxNotice === "yahoo_connected") {
      setNotice("Yahoo Mail connected successfully.");
    } else if (mailboxNotice === "yahoo_error") {
      setError("Yahoo Mail connection failed. Try again or use IMAP credentials.");
    }
  }, [mailboxNotice]);

  async function connectGmail() {
    setError(undefined);
    setBusy(true);
    try {
      const { authorization_url } = await api.gmailAuthorize();
      window.location.assign(authorization_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start Gmail OAuth.");
      setBusy(false);
    }
  }

  async function connectOutlook() {
    setError(undefined);
    setBusy(true);
    try {
      const { authorization_url } = await api.outlookAuthorize();
      window.location.assign(authorization_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start Outlook OAuth.");
      setBusy(false);
    }
  }

  async function connectYahoo() {
    setError(undefined);
    setBusy(true);
    try {
      const { authorization_url } = await api.yahooAuthorize();
      window.location.assign(authorization_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start Yahoo OAuth.");
      setBusy(false);
    }
  }

  async function saveImap() {
    setError(undefined);
    setNotice(undefined);
    setBusy(true);
    try {
      const saved = await api.upsertMailboxCredentials({
        connector_type: "imap_smtp",
        enabled: true,
        config: {
          ...imapConfig,
          smtp_user: imapConfig.smtp_user || imapConfig.imap_user,
          smtp_from: imapConfig.smtp_from || imapConfig.imap_user,
        },
      });
      setCredential(saved);
      setNotice("Mailbox credentials saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save mailbox credentials.");
    } finally {
      setBusy(false);
    }
  }

  async function testConnection() {
    setError(undefined);
    setNotice(undefined);
    setBusy(true);
    try {
      const result = await api.testMailbox(
        credential?.connector_type === "imap_smtp" ? undefined : imapConfig,
      );
      if (result.imap_ok && result.smtp_ok) {
        setNotice("Mailbox connection succeeded.");
      } else {
        setError(result.error ?? "Mailbox connection failed.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Mailbox test failed.");
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    setError(undefined);
    setNotice(undefined);
    setBusy(true);
    try {
      await api.deleteMailboxCredentials();
      setCredential(null);
      setNotice("Mailbox disconnected.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not disconnect mailbox.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Inbox automation (dev only)">
      <p>
        Connect a mailbox for recruiter email triage, ghost detection, and reply drafting. Requires{" "}
        <code>INBOX_AGENT_ENABLED=true</code> on the backend. Do not enable on hosted production.
      </p>
      {loading ? <p>Loading mailbox settings…</p> : null}
      {notice ? <Banner kind="success">{notice}</Banner> : null}
      {error ? <Banner kind="error">{error}</Banner> : null}

      {credential?.connector_type === "gmail" ? (
        <p>
          Connected Gmail: <strong>{credential.email_address}</strong>
        </p>
      ) : null}

      {credential?.connector_type === "outlook" ? (
        <p>
          Connected Outlook: <strong>{credential.email_address}</strong>
        </p>
      ) : null}

      {credential?.connector_type === "yahoo" ? (
        <p>
          Connected Yahoo Mail: <strong>{credential.email_address}</strong>
        </p>
      ) : null}

      <p>
        <Button type="button" onClick={() => void connectGmail()} disabled={busy}>
          Connect Gmail
        </Button>{" "}
        <Button type="button" onClick={() => void connectOutlook()} disabled={busy}>
          Connect Outlook
        </Button>{" "}
        <Button type="button" onClick={() => void connectYahoo()} disabled={busy}>
          Connect Yahoo
        </Button>
      </p>

      <p>Or configure IMAP + SMTP manually:</p>
      <Field label="IMAP host">
        <input
          value={imapConfig.imap_host}
          onChange={(e) => setImapConfig({ ...imapConfig, imap_host: e.target.value })}
        />
      </Field>
      <Field label="IMAP user">
        <input
          value={imapConfig.imap_user}
          onChange={(e) => setImapConfig({ ...imapConfig, imap_user: e.target.value })}
        />
      </Field>
      <Field label="IMAP password" hint="Write-only; not shown after save.">
        <input
          type="password"
          autoComplete="off"
          value={imapConfig.imap_password}
          onChange={(e) => setImapConfig({ ...imapConfig, imap_password: e.target.value })}
        />
      </Field>
      <Field label="SMTP host">
        <input
          value={imapConfig.smtp_host}
          onChange={(e) => setImapConfig({ ...imapConfig, smtp_host: e.target.value })}
        />
      </Field>
      <Field label="SMTP password">
        <input
          type="password"
          autoComplete="off"
          value={imapConfig.smtp_password}
          onChange={(e) => setImapConfig({ ...imapConfig, smtp_password: e.target.value })}
        />
      </Field>
      <p>
        <Button type="button" onClick={() => void saveImap()} disabled={busy}>
          Save IMAP credentials
        </Button>{" "}
        <Button type="button" variant="ghost" onClick={() => void testConnection()} disabled={busy}>
          Test connection
        </Button>{" "}
        {credential ? (
          <Button type="button" variant="danger" onClick={() => void disconnect()} disabled={busy}>
            Disconnect
          </Button>
        ) : null}
      </p>
    </Card>
  );
}
