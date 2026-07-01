/** Public marketing landing page shown at "/" to logged-out and logged-in visitors. */

import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Brand } from "../components/Brand";
import { PublicFooter } from "../components/PublicFooter";
import { FAQ, FEATURES, INTEGRATIONS, SHOWCASE, STEPS } from "./landing/content";

export function LandingPage() {
  const { user } = useAuth();
  const [activeShowcase, setActiveShowcase] = useState<(typeof SHOWCASE)[number]["id"]>("searches");
  const showcase = SHOWCASE.find((item) => item.id === activeShowcase) ?? SHOWCASE[0];

  return (
    <div className="landing">
      <div className="landing-glow" aria-hidden="true" />

      <header className="landing-header">
        <Brand className="landing-brand" />
        <nav className="landing-nav">
          <a href="#product" className="landing-nav-link">
            Product
          </a>
          <a href="#how-it-works" className="landing-nav-link">
            How it works
          </a>
          <a href="#faq" className="landing-nav-link">
            FAQ
          </a>
          <Link to="/pricing" className="landing-nav-link">
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
        <section className="landing-hero">
          <p className="landing-eyebrow">Job alerts that give you a head start</p>
          <h1>See new roles before the crowd.</h1>
          <p className="landing-sub">
            HeadStart watches the boards you care about, filters out the noise, and pings you the
            moment a matching role goes live — so you can apply while everyone else is still
            scrolling.
          </p>
          <div className="landing-cta">
            {user ? (
              <Link to="/app" className="btn btn-primary btn-lg">
                Open your dashboard
              </Link>
            ) : (
              <>
                <Link to="/register" className="btn btn-primary btn-lg">
                  Create a free account
                </Link>
                <Link to="/login" className="btn btn-ghost btn-lg">
                  Sign in
                </Link>
              </>
            )}
          </div>

          <div className="landing-hero-shot">
            <div
              className="landing-browser"
              role="img"
              aria-label="Screenshot of the HeadStart searches dashboard"
            >
              <div className="landing-browser-chrome" aria-hidden="true">
                <span className="landing-browser-dot" />
                <span className="landing-browser-dot" />
                <span className="landing-browser-dot" />
              </div>
              <img
                className="landing-browser-screen"
                src="/marketing/searches.png"
                alt=""
                width={1280}
                height={800}
                loading="eager"
                decoding="async"
              />
            </div>
            <img
              className="landing-hero-notify"
              src="/marketing/notification.png"
              alt="Example push notification for a new Senior Backend Engineer match"
              width={320}
              height={180}
              loading="eager"
              decoding="async"
            />
          </div>
        </section>

        <section className="landing-strip" aria-label="Supported integrations">
          <p className="landing-strip-label">Works with the boards and channels you already use</p>
          <ul className="landing-strip-list">
            {INTEGRATIONS.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
        </section>

        <section id="product" className="landing-showcase" aria-labelledby="product-title">
          <div className="landing-showcase-intro">
            <h2 id="product-title" className="landing-section-title">
              See it in action
            </h2>
            <p className="landing-showcase-lead">
              Real screens from HeadStart — configure watches, triage your feed, and get alerted the
              second a role matches.
            </p>
          </div>

          <div className="landing-showcase-tabs" role="tablist" aria-label="Product screenshots">
            {SHOWCASE.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                id={`showcase-tab-${item.id}`}
                aria-selected={activeShowcase === item.id}
                aria-controls={`showcase-panel-${item.id}`}
                className={
                  activeShowcase === item.id
                    ? "landing-showcase-tab landing-showcase-tab-active"
                    : "landing-showcase-tab"
                }
                onClick={() => setActiveShowcase(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div
            className="landing-showcase-panel"
            role="tabpanel"
            id={`showcase-panel-${showcase.id}`}
            aria-labelledby={`showcase-tab-${showcase.id}`}
          >
            <div className="landing-showcase-copy">
              <h3>{showcase.title}</h3>
              <p>{showcase.body}</p>
            </div>
            <figure className="landing-showcase-figure">
              <img src={showcase.image} alt={showcase.alt} loading="lazy" decoding="async" />
            </figure>
          </div>
        </section>

        <section id="how-it-works" className="landing-steps">
          <h2 className="landing-section-title">How it works</h2>
          <div className="landing-steps-grid">
            {STEPS.map((item) => (
              <article key={item.step} className="landing-step">
                <span className="landing-step-num">{item.step}</span>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-features" aria-label="Features">
          <h2 className="landing-section-title">Everything you need to move first</h2>
          <div className="landing-features-grid">
            {FEATURES.map((feature) => (
              <article key={feature.title} className="landing-feature">
                <h3>{feature.title}</h3>
                <p>{feature.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="faq" className="landing-faq">
          <h2 className="landing-section-title">Questions</h2>
          <dl className="landing-faq-list">
            {FAQ.map((item) => (
              <div key={item.q} className="landing-faq-item">
                <dt>{item.q}</dt>
                <dd>{item.a}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="landing-bottom-cta">
          <h2>Ready for your next head start?</h2>
          <p>Set up your first search in minutes. No credit card required.</p>
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
