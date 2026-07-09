/** Non-intrusive ads for free-tier users; paid plans and admins see nothing. */

import { Link } from "react-router-dom";
import { useMeta } from "../hooks/queries";
import { useCookieConsent } from "./CookieConsentContext";

type Props = {
  /** Sidebar card vs compact strip above mobile nav. */
  variant?: "sidebar" | "mobile";
};

export function FreeTierAd({ variant = "sidebar" }: Props) {
  const meta = useMeta();
  // Read consent from context (not localStorage) so the ad reacts when the user
  // accepts or revokes optional cookies without a page reload.
  const { choice } = useCookieConsent();
  const showAds = meta.data?.plan.show_ads ?? false;
  if (!showAds) {
    return null;
  }

  const externalSlot = meta.data?.ads.external_slot_url ?? null;
  const showExternalAd = externalSlot !== null && choice === "all";

  return (
    <aside
      className={`free-tier-ad free-tier-ad--${variant}`}
      aria-label="Sponsored"
      data-testid="free-tier-ad"
    >
      <p className="free-tier-ad-label">Sponsored</p>

      <div className="free-tier-ad-house">
        <p className="free-tier-ad-title">Go ad-free with Starter</p>
        <p className="free-tier-ad-copy">
          Remove ads with Starter, or unlock AI summaries, premium scrapers, and more on Pro.
        </p>
        <Link className="btn btn-primary free-tier-ad-cta" to="/pricing">
          View plans
        </Link>
      </div>

      {externalSlot ? (
        showExternalAd ? (
          <iframe
            className="free-tier-ad-frame"
            title="Partner advertisement"
            src={externalSlot}
            loading="lazy"
            referrerPolicy="no-referrer"
            sandbox="allow-scripts allow-popups"
          />
        ) : (
          <p className="free-tier-ad-consent muted">
            Accept optional cookies in{" "}
            <Link to="/app/settings">Settings → Privacy &amp; cookies</Link> to show partner offers
            here.
          </p>
        )
      ) : null}
    </aside>
  );
}
