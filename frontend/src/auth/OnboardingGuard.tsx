/** Redirect new accounts to the onboarding wizard until they finish or skip it. */

import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function OnboardingGuard() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="auth-screen auth-loading">Loading...</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!user.onboarding_completed_at) {
    return <Navigate to="/app/onboarding" replace />;
  }

  return <Outlet />;
}
