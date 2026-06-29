/** Email + password login. */

import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Banner, Button, Card, Field } from "../components/ui";
import { useHealth } from "../hooks/queries";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const health = useHealth();

  if (user) {
    return <Navigate to="/app" replace />;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(undefined);
    setBusy(true);
    try {
      await login(email, password);
      navigate("/app/searches", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <Card title="Sign in to JobNotifier">
        {!health.data && !health.isPending && (
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
