/** Public marketing landing page shown at "/" to logged-out and logged-in visitors. */

import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Brand } from "../components/Brand";
import { PublicFooter } from "../components/PublicFooter";

const INTEGRATIONS = [
  "Greenhouse",
  "Lever",
  "Ashby",
  "Workday",
  "Indeed",
  "LinkedIn",
  "Slack",
  "ntfy",
];

const STEPS = [
  {
    step: "1",
    title: "Connect the boards you watch",
    body: "Add company career pages and job sites — or use the browser extension to capture a search URL in one click.",
  },
  {
    step: "2",
    title: "Filter before you get pinged",
    body: "Keywords, location, workplace, salary, and cross-search dedup so you only hear about roles worth your time.",
  },
  {
    step: "3",
    title: "Apply while others are scrolling",
    body: "Instant alerts via ntfy, email, Slack, Discord, Telegram, or your own webhook — plus AI summaries of why each role fits.",
  },
];

const FEATURES = [
  {
    title: "Always watching",
    body: "HeadStart polls your sources on a schedule and catches new postings the moment they go live.",
  },
  {
    title: "Your channels, your rules",
    body: "Immediate pings or batched digests. Route alerts wherever you already live — phone, inbox, or team chat.",
  },
  {
    title: "Built for speed",
    body: "Mobile PWA, RSS export, and a focused jobs feed so you can review and act from anywhere.",
  },
];

const FAQ = [
  {
    q: "How is HeadStart different from job board alerts?",
    a: "Board alerts are broad and noisy. HeadStart watches the specific sources you choose, applies your filters server-side, deduplicates across searches, and pushes only net-new matches.",
  },
  {
    q: "Do I need to keep a tab open?",
    a: "No. HeadStart runs in the cloud on a schedule. You get notified even when your laptop is closed.",
  },
  {
    q: "Which sites are supported?",
    a: "Greenhouse, Lever, Ashby, Workday, Indeed, LinkedIn, and generic HTML career pages — with more adapters added over time.",
  },
];

export function LandingPage() {
  const { user } = useAuth();

  return (
    <div className="landing">
      <div className="landing-glow" aria-hidden="true" />

      <header className="landing-header">
        <Brand className="landing-brand" />
        <nav className="landing-nav">
          <a href="#how-it-works" className="landing-nav-link">
            How it works
          </a>
          <a href="#faq" className="landing-nav-link">
            FAQ
          </a>
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

          <div className="landing-preview" aria-hidden="true">
            <div className="landing-preview-card landing-preview-notify">
              <span className="landing-preview-label">New match</span>
              <strong>Senior Backend Engineer</strong>
              <span className="landing-preview-meta">Acme Corp · Remote · $180–210k</span>
              <span className="landing-preview-pill">Just posted</span>
            </div>
            <div className="landing-preview-card landing-preview-feed">
              <div className="landing-preview-row">
                <span className="landing-preview-dot" />
                <div>
                  <strong>Staff Platform Engineer</strong>
                  <span className="landing-preview-meta">Includes &quot;kubernetes&quot; · Amsterdam</span>
                </div>
              </div>
              <div className="landing-preview-row">
                <span className="landing-preview-dot landing-preview-dot-muted" />
                <div>
                  <strong>Product Engineer</strong>
                  <span className="landing-preview-meta">Hybrid · seen yesterday</span>
                </div>
              </div>
            </div>
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
