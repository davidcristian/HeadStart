/** Confirm email ownership via link or resend the verification email. */

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import { Banner, Button, Card } from "../components/ui";

export function VerifyEmailPage() {
  const { user, loading, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  const [message, setMessage] = useState<string>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [verifying, setVerifying] = useState(Boolean(token));

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    async function verifyFromLink() {
      setError(undefined);
      setMessage(undefined);
      setVerifying(true);
      try {
        await api.verifyEmail(token!);
        if (user) {
          await refreshUser();
        }
        if (!cancelled) {
          setMessage("Email verified. You can continue setting up HeadStart.");
          navigate("/app/onboarding", { replace: true });
        }
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      } finally {
        if (!cancelled) setVerifying(false);
      }
    }
    void verifyFromLink();
    return () => {
      cancelled = true;
    };
  }, [token, user, refreshUser, navigate]);

  if (!loading && user?.email_verified_at) {
    return <Navigate to="/app" replace />;
  }

  async function resend(e: FormEvent) {
    e.preventDefault();
    setError(undefined);
    setMessage(undefined);
    setBusy(true);
    try {
      const resp = await api.resendVerificationEmail();
      setMessage(resp.message);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <Card title="Verify your email">
        {verifying && <p className="auth-alt">Confirming your email address...</p>}
        {message && <Banner kind="success">{message}</Banner>}
        {error && <Banner kind="error">{error}</Banner>}
        {!verifying && !token && (
          <>
            <p className="auth-alt" style={{ marginTop: 0 }}>
              {user ? (
                <>
                  We sent a verification link to <strong>{user.email}</strong>. Open it to continue,
                  or request another email below.
                </>
              ) : (
                <>
                  Open the verification link from your email, or <Link to="/login">sign in</Link> to
                  resend it.
                </>
              )}
            </p>
            {user && (
              <form onSubmit={resend}>
                <Button type="submit" disabled={busy}>
                  {busy ? "Sending..." : "Resend verification email"}
                </Button>
              </form>
            )}
            {user && (
              <p className="auth-alt">
                Wrong address? <Link to="/app/settings">Manage your account</Link>
              </p>
            )}
          </>
        )}
        {!user && !loading && (
          <p className="auth-alt">
            <Link to="/login">Back to sign in</Link>
          </p>
        )}
      </Card>
    </div>
  );
}
