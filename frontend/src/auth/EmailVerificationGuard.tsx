/** Redirect unverified accounts to the email verification screen. */

import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function EmailVerificationGuard() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="auth-screen auth-loading">Loading...</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!user.email_verified_at) {
    return <Navigate to="/verify-email" replace />;
  }

  return <Outlet />;
}
