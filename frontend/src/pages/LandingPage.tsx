/** Public marketing landing page shown at "/" to logged-out and logged-in visitors. */

import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const FEATURES = [
  {
    title: "Watch the boards you care about",
    body: "Greenhouse, Lever, Ashby, Workday, Indeed, LinkedIn and generic HTML — add a source and JobNotifier polls it for you.",
  },
  {
    title: "Get alerted your way",
    body: "ntfy, email, Slack, Discord, Telegram or your own webhook. Immediate pings or batched digests, your choice.",
  },
  {
    title: "Cut the noise",
    body: "Keyword include/exclude, location, workplace and salary filters, plus cross-search dedup so you only hear about a role once.",
  },
];

export function LandingPage() {
  const { user } = useAuth();

  return (
    <div className="landing">
      <header className="landing-header">
        <Link to="/" className="brand landing-brand">
          <span className="brand-mark">JN</span>
          <span className="brand-name">JobNotifier</span>
        </Link>
        <nav className="landing-nav">
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
          <h1>Never miss the job you actually want.</h1>
          <p className="landing-sub">
            JobNotifier watches the job boards and company career pages you choose, filters out
            the noise, and pings you the moment a matching role goes live.
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
        </section>

        <section className="landing-features" aria-label="Features">
          {FEATURES.map((feature) => (
            <article key={feature.title} className="landing-feature">
              <h2>{feature.title}</h2>
              <p>{feature.body}</p>
            </article>
          ))}
        </section>
      </main>

      <footer className="landing-footer">
        <span className="landing-footer-copy">
          &copy; {new Date().getFullYear()} JobNotifier
        </span>
        <nav className="landing-footer-nav">
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
    </div>
  );
}
