/** Gate that requires an authenticated admin; redirects non-admins to searches. */

import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function AdminRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="auth-screen auth-loading">Loading...</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!user.is_admin) {
    return <Navigate to="/searches" replace />;
  }
  return <Outlet />;
}
