/** Public pricing page with tier cards, comparison table, and billing toggle. */

import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import { Brand } from "../components/Brand";
import { PromoCodeField } from "../components/PromoCodeField";
import { ComparisonCell, PlanCta } from "../components/pricing/PricingParts";
import { PublicFooter } from "../components/PublicFooter";
import type { PromoValidation } from "../types";
import {
  COMPARISON_ROWS,
  PLANS,
  PRICING_FAQ,
  type BillingPeriod,
  annualBilledTotal,
  formatUsd,
  planDisplayPrice,
} from "../lib/pricing";

export function PricingPage() {
  const { user } = useAuth();
  const [billingPeriod, setBillingPeriod] = useState<BillingPeriod>("monthly");
  const [checkoutError, setCheckoutError] = useState<string>();
  const [checkingOut, setCheckingOut] = useState(false);
  const [appliedPromo, setAppliedPromo] = useState<PromoValidation | null>(null);

  async function startProCheckout() {
    setCheckoutError(undefined);
    if (!user) return;
    setCheckingOut(true);
    try {
      const { url } = await api.createCheckout(billingPeriod, appliedPromo?.code);
      window.location.assign(url);
    } catch (err) {
      setCheckoutError(err instanceof Error ? err.message : "Could not start checkout.");
      setCheckingOut(false);
    }
  }

  return (
    <div className="landing pricing-page">
      <div className="landing-glow" aria-hidden="true" />

      <header className="landing-header">
        <Brand className="landing-brand" />
        <nav className="landing-nav">
          <Link to="/" className="landing-nav-link">
            Home
          </Link>
          <Link
            to="/pricing"
            className="landing-nav-link landing-nav-link-active"
            aria-current="page"
          >
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

        {checkoutError ? (
          <p className="pricing-billing-note" role="alert">
            {checkoutError}
          </p>
        ) : null}

        {user ? (
          <section className="pricing-promo" aria-label="Promo code">
            <PromoCodeField onApplied={setAppliedPromo} disabled={checkingOut} />
          </section>
        ) : null}

        <section className="pricing-cards" aria-label="Plans">
          {PLANS.map((plan) => {
            const price = planDisplayPrice(plan, billingPeriod);
            const isFree = plan.id === "free";

            return (
              <article
                key={plan.id}
                className={plan.highlight ? "pricing-card pricing-card-highlight" : "pricing-card"}
              >
                {plan.highlight ? <span className="pricing-card-badge">Best value</span> : null}
                <header className="pricing-card-header">
                  <h2>{plan.name}</h2>
                  <p className="pricing-card-desc">{plan.description}</p>
                  <div className="pricing-card-price">
                    <span className="pricing-card-amount">{formatUsd(price)}</span>
                    <span className="pricing-card-period">/ month</span>
                  </div>
                  {!isFree && billingPeriod === "annual" ? (
                    <p className="pricing-card-billed">
                      Billed annually ({formatUsd(annualBilledTotal(plan))}/yr)
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

                <PlanCta
                  plan={plan}
                  user={user}
                  checkingOut={checkingOut}
                  onCheckout={() => void startProCheckout()}
                />
              </article>
            );
          })}
        </section>

        <p className="pricing-billing-note">
          Pro includes a 14-day free trial when billing is enabled on the server. Starter and Plus
          self-serve checkout is rolling out soon — create a free account to get started today.
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
                  {PLANS.map((plan) => (
                    <th key={plan.id} scope="col">
                      {plan.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {COMPARISON_ROWS.map((row) => (
                  <tr key={row.label}>
                    <th scope="row">{row.label}</th>
                    {PLANS.map((plan) => (
                      <td key={plan.id}>
                        <ComparisonCell value={row[plan.id]} />
                      </td>
                    ))}
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
