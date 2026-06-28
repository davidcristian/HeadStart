/** Set a new password from an email reset link (?token=...). */

import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Banner, Button, Card, Field } from "../components/ui";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState<string>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(undefined);
    if (!token) {
      setError("Reset link is missing or invalid. Request a new one.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      const resp = await api.resetPassword(token, password);
      setMessage(resp.message);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <Card title="Choose a new password">
        {!token && (
          <Banner kind="error">
            This reset link is invalid. <Link to="/forgot-password">Request a new one</Link>.
          </Banner>
        )}
        {message && <Banner kind="success">{message}</Banner>}
        {error && <Banner kind="error">{error}</Banner>}
        {!message && token && (
          <form onSubmit={submit}>
            <Field label="New password" hint="At least 8 characters.">
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                minLength={8}
                required
              />
            </Field>
            <Field label="Confirm new password">
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                autoComplete="new-password"
                required
              />
            </Field>
            <Button type="submit" disabled={busy}>
              {busy ? "Updating..." : "Update password"}
            </Button>
          </form>
        )}
        <p className="auth-alt">
          {message ? (
            <Link to="/login">Sign in</Link>
          ) : (
            <Link to="/forgot-password">Request a new reset link</Link>
          )}
        </p>
      </Card>
    </div>
  );
}
