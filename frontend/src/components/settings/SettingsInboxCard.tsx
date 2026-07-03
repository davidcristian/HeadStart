/** Dev-only inbox mailbox settings (IMAP/SMTP, Gmail OAuth, Outlook OAuth, or Yahoo OAuth). */

import { useEffect, useState } from "react";
import { Banner, Button, Card } from "../ui";
import { SettingsInboxFastmailForm } from "./SettingsInboxFastmailForm";
import { SettingsInboxImapForm } from "./SettingsInboxImapForm";
import { api } from "../../api";
import type { FastmailConfig, MailboxConfig, MailboxCredential } from "../../types";

const EMPTY_IMAP_CONFIG: MailboxConfig = {
  imap_host: "imap.gmail.com",
  imap_user: "",
  imap_password: "",
  smtp_host: "smtp.gmail.com",
  smtp_password: "",
  smtp_from: "",
};

const EMPTY_FASTMAIL_CONFIG: FastmailConfig = {
  email_address: "",
  api_token: "",
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
  const [fastmailConfig, setFastmailConfig] = useState<FastmailConfig>(EMPTY_FASTMAIL_CONFIG);
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
          if (row.connector_type === "fastmail" && row.email_address) {
            const emailAddress = row.email_address;
            setFastmailConfig((current) => ({
              ...current,
              email_address: emailAddress,
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

  async function saveFastmail() {
    setError(undefined);
    setNotice(undefined);
    setBusy(true);
    try {
      const saved = await api.upsertMailboxCredentials({
        connector_type: "fastmail",
        enabled: true,
        config: fastmailConfig,
      });
      setCredential(saved);
      setFastmailConfig((current) => ({ ...current, api_token: "" }));
      setNotice("Fastmail credentials saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save Fastmail credentials.");
    } finally {
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
        credential ? undefined : { connector_type: "imap_smtp", config: imapConfig },
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

      {credential?.connector_type === "fastmail" ? (
        <p>
          Connected Fastmail: <strong>{credential.email_address}</strong>
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

      <SettingsInboxFastmailForm
        fastmailConfig={fastmailConfig}
        busy={busy}
        onChange={setFastmailConfig}
        onSave={() => void saveFastmail()}
      />

      <SettingsInboxImapForm
        imapConfig={imapConfig}
        busy={busy}
        hasCredential={Boolean(credential)}
        onChange={setImapConfig}
        onSave={() => void saveImap()}
        onTest={() => void testConnection()}
        onDisconnect={() => void disconnect()}
      />
    </Card>
  );
}
