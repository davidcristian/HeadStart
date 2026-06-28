import { Navigate, Route, Routes } from "react-router-dom";
import { AdminRoute } from "./auth/AdminRoute";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Layout } from "./components/Layout";
import { AdminPage } from "./pages/AdminPage";
import { CredentialsPage } from "./pages/CredentialsPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { JobsPage } from "./pages/JobsPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { SearchesPage } from "./pages/SearchesPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SourcesPage } from "./pages/SourcesPage";
import { TargetsPage } from "./pages/TargetsPage";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/searches" replace />} />
          <Route path="/searches" element={<SearchesPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/sources" element={<SourcesPage />} />
          <Route path="/targets" element={<TargetsPage />} />
          <Route path="/credentials" element={<CredentialsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route element={<AdminRoute />}>
            <Route path="/admin" element={<AdminPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/searches" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
