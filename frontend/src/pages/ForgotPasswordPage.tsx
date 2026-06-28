/** Request a password-reset email. */

import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Banner, Button, Card, Field } from "../components/ui";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(undefined);
    setMessage(undefined);
    setBusy(true);
    try {
      const resp = await api.forgotPassword(email);
      setMessage(resp.message);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <Card title="Reset your password">
        <p className="auth-alt" style={{ marginTop: 0 }}>
          Enter your account email and we&apos;ll send a link to choose a new password.
        </p>
        {message && <Banner kind="success">{message}</Banner>}
        {error && <Banner kind="error">{error}</Banner>}
        {!message && (
          <form onSubmit={submit}>
            <Field label="Email">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
            </Field>
            <Button type="submit" disabled={busy}>
              {busy ? "Sending..." : "Send reset link"}
            </Button>
          </form>
        )}
        <p className="auth-alt">
          <Link to="/login">Back to sign in</Link>
        </p>
      </Card>
    </div>
  );
}
