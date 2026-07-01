/** Redirect unverified accounts to the email verification screen. */

import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function EmailVerificationGuard() {
  const { user } = useAuth();

  if (user && !user.email_verified_at) {
    return <Navigate to="/verify-email" replace />;
  }

  return <Outlet />;
}
