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

      <Card title="Receiving notifications (ntfy)">
        <ol className="help-list">
          <li>
            Install the <strong>ntfy</strong> app (iOS / Android) or open{" "}
            <a href="https://ntfy.sh" target="_blank" rel="noreferrer">
              ntfy.sh
            </a>
            .
          </li>
          <li>
            Create a Notification target on the <strong>Notifications</strong> page with your chosen
            topic (pick something unguessable).
          </li>
          <li>Subscribe to that exact topic in the ntfy app.</li>
          <li>Use "Send test" to confirm delivery, then attach the target to a search.</li>
        </ol>
      </Card>
    </>
  );
}
