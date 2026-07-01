/** Footer links shared by the landing page and public legal pages. */

import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Brand } from "./Brand";
import { useCookieConsent } from "./CookieConsentContext";

export function PublicFooter() {
  const { user } = useAuth();
  const { openCookieSettings } = useCookieConsent();

  return (
    <footer className="landing-footer">
      <Brand className="landing-footer-brand" />
      <span className="landing-footer-copy">&copy; {new Date().getFullYear()} HeadStart</span>
      <nav className="landing-footer-nav" aria-label="Footer">
        <Link to="/pricing">Pricing</Link>
        <Link to="/privacy">Privacy</Link>
        <Link to="/terms">Terms</Link>
        <Link to="/impressum">Impressum</Link>
        <button type="button" className="landing-footer-link" onClick={openCookieSettings}>
          Cookie settings
        </button>
        {user ? (
          <Link to="/app">Go to app</Link>
        ) : (
          <>
            <Link to="/login">Sign in</Link>
            <Link to="/register">Get started</Link>
          </>
        )}
      </nav>
    </footer>
  );
}
