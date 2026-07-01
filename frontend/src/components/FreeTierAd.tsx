/** Non-intrusive ads for free-tier users; paid plans and admins see nothing. */

import { Link } from "react-router-dom";
import { useMeta } from "../hooks/queries";
import { acceptsOptionalCookies } from "../lib/cookieConsent";

type Props = {
  /** Sidebar card vs compact strip above mobile nav. */
  variant?: "sidebar" | "mobile";
};

export function FreeTierAd({ variant = "sidebar" }: Props) {
  const meta = useMeta();
  const showAds = meta.data?.plan.show_ads ?? false;
  if (!showAds) {
    return null;
  }

  const externalSlot = meta.data?.ads.external_slot_url ?? null;
  const showExternalAd = externalSlot !== null && acceptsOptionalCookies();

  return (
    <aside
      className={`free-tier-ad free-tier-ad--${variant}`}
      aria-label="Sponsored"
      data-testid="free-tier-ad"
    >
      <p className="free-tier-ad-label">Sponsored</p>

      <div className="free-tier-ad-house">
        <p className="free-tier-ad-title">Go ad-free with Pro</p>
        <p className="free-tier-ad-copy">
          Unlock digest mode, AI summaries, premium scrapers, and more — without sponsored messages.
        </p>
        <Link className="btn btn-primary free-tier-ad-cta" to="/pricing">
          View Pro plans
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
            sandbox="allow-scripts allow-same-origin allow-popups"
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
