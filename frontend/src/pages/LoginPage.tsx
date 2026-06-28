/** Email + password login. */

import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import { Banner, Button, Card, Field } from "../components/ui";
import { useAsync } from "../hooks/useAsync";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const health = useAsync(() => api.health(), []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(undefined);
    setBusy(true);
    try {
      await login(email, password);
      navigate("/searches", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <Card title="Sign in to JobNotifier">
        {!health.data && !health.loading && (
          <Banner kind="error">API unreachable. Check the URL on the Settings screen.</Banner>
        )}
        {error && <Banner kind="error">{error}</Banner>}
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
          <Field label="Password">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </Field>
          <Button type="submit" disabled={busy}>
            {busy ? "Signing in..." : "Sign in"}
          </Button>
        </form>
        <p className="auth-alt">
          <Link to="/forgot-password">Forgot password?</Link>
        </p>
        <p className="auth-alt">
          No account? <Link to="/register">Create one</Link>
        </p>
      </Card>
    </div>
  );
}
