/** Connection settings (API base URL) and ntfy help. Auth is via sign-in. */

import { useState } from "react";
import { Banner, Button, Card, Field } from "../components/ui";
import { getApiBaseUrl, setApiBaseUrl } from "../lib/settings";

export function SettingsPage() {
  const [baseUrl, setBaseUrl] = useState(getApiBaseUrl());
  const [saved, setSaved] = useState(false);

  function save() {
    setApiBaseUrl(baseUrl);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <>
      <h1>Settings</h1>
      <Card title="API connection">
        {saved && <Banner kind="success">Saved.</Banner>}
        <Field label="API base URL" hint="Where the backend is reachable from your browser.">
          <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
        </Field>
        <Button onClick={save}>Save</Button>
      </Card>

      <Card title="Receiving notifications">
        <p>
          JobNotifier can deliver alerts via <strong>email</strong> (configure <code>SMTP_*</code>{" "}
          on the server), <strong>Slack</strong> (incoming webhook), or <strong>ntfy</strong> push
          (no server mail setup required).
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
