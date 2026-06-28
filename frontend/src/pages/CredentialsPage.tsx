/** Manage per-site credentials (cookies/headers/session) used by scrapers.
 *
 * Secrets are write-only: once saved, the API returns only booleans indicating
 * what is stored. To change a secret, save the credential again.
 */

import { useState } from "react";
import { api } from "../api";
import { JsonEditor } from "../components/JsonEditor";
import { Badge, Banner, Button, Card, EmptyState, Field } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import type { Json } from "../types";

function asStringMap(value: Json): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(value)) out[k] = String(v);
  return out;
}

export function CredentialsPage() {
  const credentials = useAsync(() => api.listCredentials(), []);
  const sources = useAsync(() => api.listSources(), []);
  const [error, setError] = useState<string>();

  const [sourceId, setSourceId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [cookies, setCookies] = useState<Json>({});
  const [headers, setHeaders] = useState<Json>({});
  const [session, setSession] = useState<Json>({});
  const [valid, setValid] = useState({ cookies: true, headers: true, session: true });

  const sourceList = sources.data ?? [];
  const effectiveSource = sourceId ?? sourceList[0]?.id ?? null;
  const allValid = valid.cookies && valid.headers && valid.session;

  function sourceName(id: number): string {
    return sourceList.find((s) => s.id === id)?.name ?? `Source ${id}`;
  }

  async function create() {
    setError(undefined);
    if (effectiveSource === null) {
      setError("Create a source first.");
      return;
    }
    try {
      await api.createCredential({
        source_id: effectiveSource,
        name,
        enabled: true,
        cookies: asStringMap(cookies),
        headers: asStringMap(headers),
        session: asStringMap(session),
      });
      setName("");
      setCookies({});
      setHeaders({});
      setSession({});
      credentials.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function toggle(id: number, enabled: boolean) {
    await api.updateCredential(id, { enabled });
    credentials.reload();
  }

  async function remove(id: number) {
    await api.deleteCredential(id);
    credentials.reload();
  }

  return (
    <>
      <h1>Site credentials</h1>
      <p className="muted">
        Attach cookies or headers from a logged-in browser session to a source. The worker injects
        them into requests for that source, which can bypass bot/captcha walls. Secrets are
        encrypted at rest and never shown again after saving.
      </p>

      <Card title="Add a credential">
        {error && <Banner kind="error">{error}</Banner>}
        {sourceList.length === 0 ? (
          <EmptyState>Create a source first, then add credentials for it.</EmptyState>
        ) : (
          <>
            <div className="form-grid">
              <Field label="Source">
                <select
                  value={effectiveSource ?? ""}
                  onChange={(e) => setSourceId(Number(e.target.value))}
                >
                  {sourceList.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Name" hint="A label to recognize this credential.">
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="My logged-in session"
                />
              </Field>
            </div>
            <Field label="Cookies (JSON)" hint='e.g. {"sessionid": "abc123"}'>
              <JsonEditor
                value={cookies}
                onChange={(v, ok) => {
                  setCookies(v);
                  setValid((s) => ({ ...s, cookies: ok }));
                }}
              />
            </Field>
            <Field label="Headers (JSON)" hint='e.g. {"Authorization": "Bearer ..."}'>
              <JsonEditor
                value={headers}
                onChange={(v, ok) => {
                  setHeaders(v);
                  setValid((s) => ({ ...s, headers: ok }));
                }}
              />
            </Field>
            <Field label="Session (JSON, optional)" hint="Free-form session blob for future use.">
              <JsonEditor
                value={session}
                onChange={(v, ok) => {
                  setSession(v);
                  setValid((s) => ({ ...s, session: ok }));
                }}
              />
            </Field>
            <Button onClick={create} disabled={!allValid}>
              Save credential
            </Button>
          </>
        )}
      </Card>

      <Card title="Stored credentials">
        {credentials.loading && <p>Loading...</p>}
        {credentials.data && credentials.data.length === 0 && (
          <EmptyState>No credentials stored.</EmptyState>
        )}
        {credentials.data && credentials.data.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Name</th>
                <th>Contains</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {credentials.data.map((c) => (
                <tr key={c.id}>
                  <td>{sourceName(c.source_id)}</td>
                  <td>{c.name || <span className="muted">(unnamed)</span>}</td>
                  <td>
                    {c.has_cookies && <code>cookies</code>} {c.has_headers && <code>headers</code>}{" "}
                    {c.has_session && <code>session</code>}
                    {!c.has_cookies && !c.has_headers && !c.has_session && (
                      <span className="muted">empty</span>
                    )}
                  </td>
                  <td>
                    <Badge on={c.enabled} />
                  </td>
                  <td className="row-actions">
                    <Button variant="ghost" onClick={() => toggle(c.id, !c.enabled)}>
                      {c.enabled ? "Disable" : "Enable"}
                    </Button>
                    <Button variant="danger" onClick={() => remove(c.id)}>
                      Delete
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
