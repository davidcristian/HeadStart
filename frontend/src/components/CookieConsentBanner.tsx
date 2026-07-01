/** Fixed bottom banner for essential vs optional cookie consent (GDPR baseline). */

import { Link } from "react-router-dom";
import { useCookieConsent } from "./CookieConsentContext";
import { Button } from "./ui";

export function CookieConsentBanner() {
  const { visible, setChoice } = useCookieConsent();

  if (!visible) return null;

  return (
    <div
      className="cookie-consent"
      role="dialog"
      aria-labelledby="cookie-consent-title"
      aria-describedby="cookie-consent-description"
    >
      <div className="cookie-consent-inner">
        <div className="cookie-consent-text">
          <p id="cookie-consent-title" className="cookie-consent-heading">
            Cookies on HeadStart
          </p>
          <p id="cookie-consent-description">
            We use a strictly necessary httpOnly cookie to keep you signed in. Your consent choice
            is saved in this browser. Optional cookies for advertising or analytics are not loaded
            today; choose &quot;Accept all&quot; only if you are fine enabling them when we add
            those features. See our{" "}
            <Link to="/privacy">Privacy Policy</Link> for details.
          </p>
        </div>
        <div className="cookie-consent-actions">
          <Button type="button" variant="ghost" onClick={() => setChoice("essential")}>
            Essential only
          </Button>
          <Button type="button" onClick={() => setChoice("all")}>
            Accept all
          </Button>
        </div>
      </div>
    </div>
  );
}
