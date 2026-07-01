/** Public pricing page with tier cards, comparison table, and billing toggle. */

import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Brand } from "../components/Brand";
import { PublicFooter } from "../components/PublicFooter";
import {
  COMPARISON_ROWS,
  PLANS,
  PRICING_FAQ,
  type BillingPeriod,
  formatUsd,
  planDisplayPrice,
} from "../lib/pricing";

function ComparisonCell({ value }: { value: string | boolean }) {
  if (typeof value === "boolean") {
    return (
      <span className={value ? "pricing-check" : "pricing-dash"} aria-label={value ? "Included" : "Not included"}>
        {value ? "✓" : "—"}
      </span>
    );
  }
  return <span>{value}</span>;
}

export function PricingPage() {
  const { user } = useAuth();
  const [billingPeriod, setBillingPeriod] = useState<BillingPeriod>("monthly");

  return (
    <div className="landing pricing-page">
      <div className="landing-glow" aria-hidden="true" />

      <header className="landing-header">
        <Brand className="landing-brand" />
        <nav className="landing-nav">
          <Link to="/" className="landing-nav-link">
            Home
          </Link>
          <Link to="/pricing" className="landing-nav-link landing-nav-link-active" aria-current="page">
            Pricing
          </Link>
          {user ? (
            <Link to="/app" className="btn btn-primary">
              Go to app
            </Link>
          ) : (
            <>
              <Link to="/login" className="btn btn-ghost">
                Sign in
              </Link>
              <Link to="/register" className="btn btn-primary">
                Get started
              </Link>
            </>
          )}
        </nav>
      </header>

      <main>
        <section className="pricing-hero">
          <p className="landing-eyebrow">Simple, transparent pricing</p>
          <h1>Pay for signal, not noise.</h1>
          <p className="landing-sub">
            Start free with a few watches. Upgrade when you need more searches, smarter alerts, and
            the boards that require credentials.
          </p>

          <div className="pricing-toggle" role="group" aria-label="Billing period">
            <button
              type="button"
              className={
                billingPeriod === "monthly"
                  ? "pricing-toggle-btn pricing-toggle-btn-active"
                  : "pricing-toggle-btn"
              }
              aria-pressed={billingPeriod === "monthly"}
              onClick={() => setBillingPeriod("monthly")}
            >
              Monthly
            </button>
            <button
              type="button"
              className={
                billingPeriod === "annual"
                  ? "pricing-toggle-btn pricing-toggle-btn-active"
                  : "pricing-toggle-btn"
              }
              aria-pressed={billingPeriod === "annual"}
              onClick={() => setBillingPeriod("annual")}
            >
              Annual
              <span className="pricing-toggle-badge">Save ~17%</span>
            </button>
          </div>
        </section>

        <section className="pricing-cards" aria-label="Plans">
          {PLANS.map((plan) => {
            const price = planDisplayPrice(plan, billingPeriod);
            const isFree = plan.id === "free";
            const ctaHref = isFree || plan.id === "pro" ? "/register" : "mailto:support@headstart.app?subject=HeadStart%20Team%20plan";

            return (
              <article
                key={plan.id}
                className={
                  plan.highlight ? "pricing-card pricing-card-highlight" : "pricing-card"
                }
              >
                {plan.highlight ? <span className="pricing-card-badge">Most popular</span> : null}
                <header className="pricing-card-header">
                  <h2>{plan.name}</h2>
                  <p className="pricing-card-desc">{plan.description}</p>
                  <div className="pricing-card-price">
                    <span className="pricing-card-amount">{formatUsd(price)}</span>
                    <span className="pricing-card-period">/ month</span>
                  </div>
                  {!isFree && billingPeriod === "annual" ? (
                    <p className="pricing-card-billed">
                      Billed annually ({formatUsd(price * 12)}/yr)
                    </p>
                  ) : null}
                  {!isFree && billingPeriod === "monthly" ? (
                    <p className="pricing-card-billed">Billed monthly</p>
                  ) : null}
                </header>

                <dl className="pricing-card-limits">
                  <div>
                    <dt>Searches</dt>
                    <dd>{plan.limits.searches}</dd>
                  </div>
                  <div>
                    <dt>Sources</dt>
                    <dd>{plan.limits.sources}</dd>
                  </div>
                  <div>
                    <dt>Channels</dt>
                    <dd>{plan.limits.targets}</dd>
                  </div>
                </dl>

                <ul className="pricing-card-features">
                  {plan.features.map((feature) => (
                    <li
                      key={feature.label}
                      className={feature.included ? undefined : "pricing-feature-muted"}
                    >
                      <span aria-hidden="true">{feature.included ? "✓" : "—"}</span>
                      {feature.label}
                    </li>
                  ))}
                </ul>

                {ctaHref.startsWith("mailto:") ? (
                  <a href={ctaHref} className={plan.highlight ? "btn btn-primary btn-block" : "btn btn-ghost btn-block"}>
                    {plan.cta}
                  </a>
                ) : (
                  <Link
                    to={ctaHref}
                    className={plan.highlight ? "btn btn-primary btn-block" : "btn btn-ghost btn-block"}
                  >
                    {plan.cta}
                  </Link>
                )}
              </article>
            );
          })}
        </section>

        <p className="pricing-billing-note">
          Paid checkout is coming soon — every plan above is available to try on the Free tier today
          while we finish billing integration.
        </p>

        <section className="pricing-compare" aria-labelledby="compare-title">
          <h2 id="compare-title" className="landing-section-title">
            Compare plans
          </h2>
          <div className="pricing-table-wrap">
            <table className="pricing-table">
              <thead>
                <tr>
                  <th scope="col">Feature</th>
                  <th scope="col">Free</th>
                  <th scope="col">Pro</th>
                  <th scope="col">Team</th>
                </tr>
              </thead>
              <tbody>
                {COMPARISON_ROWS.map((row) => (
                  <tr key={row.label}>
                    <th scope="row">{row.label}</th>
                    <td>
                      <ComparisonCell value={row.free} />
                    </td>
                    <td>
                      <ComparisonCell value={row.pro} />
                    </td>
                    <td>
                      <ComparisonCell value={row.team} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="landing-faq pricing-faq" aria-labelledby="pricing-faq-title">
          <h2 id="pricing-faq-title" className="landing-section-title">
            Billing questions
          </h2>
          <dl className="landing-faq-list">
            {PRICING_FAQ.map((item) => (
              <div key={item.q} className="landing-faq-item">
                <dt>{item.q}</dt>
                <dd>{item.a}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="landing-bottom-cta">
          <h2>Start with a free account</h2>
          <p>No credit card required. Set up your first search in minutes.</p>
          {user ? (
            <Link to="/app" className="btn btn-primary btn-lg">
              Open your dashboard
            </Link>
          ) : (
            <Link to="/register" className="btn btn-primary btn-lg">
              Create a free account
            </Link>
          )}
        </section>
      </main>

      <PublicFooter />
    </div>
  );
}
