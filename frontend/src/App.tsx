import { Navigate, Route, Routes } from "react-router-dom";
import { AdminRoute } from "./auth/AdminRoute";
import { EmailVerificationGuard } from "./auth/EmailVerificationGuard";
import { OnboardingGuard } from "./auth/OnboardingGuard";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Layout } from "./components/Layout";
import { ApplicationsPage } from "./pages/ApplicationsPage";
import { AdminPage } from "./pages/AdminPage";
import { CredentialsPage } from "./pages/CredentialsPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { JobsPage } from "./pages/JobsPage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { PortalsPage } from "./pages/PortalsPage";
import { PricingPage } from "./pages/PricingPage";
import { ImpressumPage } from "./pages/ImpressumPage";
import { PrivacyPolicyPage } from "./pages/PrivacyPolicyPage";
import { SubprocessorsPage } from "./pages/SubprocessorsPage";
import { TermsOfUsePage } from "./pages/TermsOfUsePage";
import { VerifyEmailPage } from "./pages/VerifyEmailPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RegisterPage } from "./pages/RegisterPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { SearchesPage } from "./pages/SearchesPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SourcesPage } from "./pages/SourcesPage";
import { TargetsPage } from "./pages/TargetsPage";

// Paths the authenticated product lived at before the public/app split. Kept as
// redirects so old bookmarks and installed PWAs land in the right place.
const LEGACY_APP_PATHS = [
  "searches",
  "jobs",
  "applications",
  "sources",
  "portals",
  "targets",
  "credentials",
  "profile",
  "settings",
  "admin",
];

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/pricing" element={<PricingPage />} />
      <Route path="/privacy" element={<PrivacyPolicyPage />} />
      <Route path="/subprocessors" element={<SubprocessorsPage />} />
      <Route path="/terms" element={<TermsOfUsePage />} />
      <Route path="/impressum" element={<ImpressumPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />

      <Route path="/app" element={<ProtectedRoute />}>
        <Route path="settings" element={<SettingsPage />} />
        <Route element={<EmailVerificationGuard />}>
          <Route path="onboarding" element={<OnboardingPage />} />
          <Route element={<OnboardingGuard />}>
            <Route element={<Layout />}>
              <Route index element={<Navigate to="/app/searches" replace />} />
              <Route path="searches" element={<SearchesPage />} />
              <Route path="jobs" element={<JobsPage />} />
              <Route path="applications" element={<ApplicationsPage />} />
              <Route path="sources" element={<SourcesPage />} />
              <Route path="portals" element={<PortalsPage />} />
              <Route path="targets" element={<TargetsPage />} />
              <Route path="credentials" element={<CredentialsPage />} />
              <Route path="profile" element={<ProfilePage />} />
              <Route element={<AdminRoute />}>
                <Route path="admin" element={<AdminPage />} />
              </Route>
              <Route path="*" element={<Navigate to="/app/searches" replace />} />
            </Route>
          </Route>
        </Route>
      </Route>

      {LEGACY_APP_PATHS.map((path) => (
        <Route key={path} path={`/${path}`} element={<Navigate to={`/app/${path}`} replace />} />
      ))}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
