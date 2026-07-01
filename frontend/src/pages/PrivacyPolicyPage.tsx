/** Public privacy policy for HeadStart. */

import { LegalPageLayout } from "../components/LegalPageLayout";

const EFFECTIVE_DATE = "June 28, 2026";

export function PrivacyPolicyPage() {
  return (
    <LegalPageLayout title="Privacy Policy" effectiveDate={EFFECTIVE_DATE}>
      <p>
        HeadStart (&quot;we&quot;, &quot;us&quot;) helps you monitor job boards and receive alerts
        when matching roles are posted. This policy describes what personal data we process when you
        use the service and how we handle it.
      </p>

      <section>
        <h2>Data we collect</h2>
        <ul>
          <li>
            <strong>Account data:</strong> email address and a hashed password used to authenticate
            you.
          </li>
          <li>
            <strong>Configuration data:</strong> job sources, searches, filters, notification
            targets, and related settings you create in the app.
          </li>
          <li>
            <strong>Site credentials (optional):</strong> cookies or headers you provide for
            authenticated scraping. These are encrypted at rest with a server-side key.
          </li>
          <li>
            <strong>Application profile (optional):</strong> contact details, links, resume text,
            cover-letter templates, and custom answers you save for applications. This is encrypted
            at rest.
          </li>
          <li>
            <strong>Job and activity data:</strong> postings discovered by your searches, your
            status labels (seen, applied, archived), delivery logs, and scrape run metadata.
          </li>
          <li>
            <strong>Technical data:</strong> API access logs, error reports, and operational metrics
            needed to run and secure the service.
          </li>
        </ul>
      </section>

      <section>
        <h2>How we use your data</h2>
        <p>We use the data above to:</p>
        <ul>
          <li>Run scheduled scrapes and match results against your filters.</li>
          <li>Deliver notifications through the channels you configure.</li>
          <li>Power the jobs feed, RSS export, and optional AI summaries of why a role matches.</li>
          <li>Maintain your account, enforce access controls, and improve reliability.</li>
        </ul>
        <p>We do not sell your personal data. We do not use your data for advertising profiles.</p>
      </section>

      <section>
        <h2>Third parties and subprocessors</h2>
        <p>Depending on how you configure HeadStart, data may be sent to:</p>
        <ul>
          <li>
            <strong>Job boards and career sites</strong> you ask us to monitor (for scraping only).
          </li>
          <li>
            <strong>Notification providers</strong> you choose (for example ntfy, email via SMTP,
            Slack, Discord, Telegram, or a custom webhook URL).
          </li>
          <li>
            <strong>AI summary providers</strong> when enabled (for example OpenAI) — only the job
            title, company, location, and filter context needed to generate a short blurb.
          </li>
          <li>
            <strong>Infrastructure providers</strong> that host the application and database when
            you use a deployed instance (for example AWS).
          </li>
        </ul>
        <p>
          You are responsible for ensuring your use of third-party job boards and notification
          services complies with their terms.
        </p>
      </section>

      <section>
        <h2>Cookies and session storage</h2>
        <p>
          HeadStart uses an httpOnly refresh-token cookie to keep you signed in between visits. The
          short-lived access token is kept in browser memory, not localStorage. We do not use
          third-party advertising or analytics cookies in the product UI.
        </p>
      </section>

      <section>
        <h2>Retention</h2>
        <p>
          We retain account and configuration data while your account is active. Job postings and
          delivery history are kept to power your feed and diagnostics. When you delete resources in
          the app, associated rows are removed from our database. You can export all of your data or
          permanently delete your account from <strong>Settings → Your account</strong> in the app.
        </p>
      </section>

      <section>
        <h2>Security</h2>
        <p>
          Passwords are hashed. Sensitive fields (site credentials and application profiles) are
          encrypted at rest. API access requires authentication, and user-owned data is scoped to
          the signed-in account. No security measure is perfect; do not store secrets in
          notification target configs that you cannot rotate.
        </p>
      </section>

      <section>
        <h2>Your rights</h2>
        <p>
          Depending on where you live, you may have rights to access, correct, delete, or export
          your personal data, and to object to or restrict certain processing. To exercise these
          rights, contact the operator of the HeadStart instance you use.
        </p>
      </section>

      <section>
        <h2>Children</h2>
        <p>
          HeadStart is not directed at children under 16, and we do not knowingly collect their
          personal data.
        </p>
      </section>

      <section>
        <h2>Changes</h2>
        <p>
          We may update this policy as the product evolves. Material changes will be reflected on
          this page with a new effective date.
        </p>
      </section>

      <section>
        <h2>Contact</h2>
        <p>
          Questions about this policy? Reach out to the administrator of the HeadStart deployment
          you are using, or the contact address published on that instance&apos;s landing page.
        </p>
      </section>
    </LegalPageLayout>
  );
}
