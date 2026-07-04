/** Public privacy policy for HeadStart. */

import { Link } from "react-router-dom";
import { LegalPageLayout } from "../components/LegalPageLayout";

const EFFECTIVE_DATE = "July 10, 2026";

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
            <strong>Auto-apply audit data:</strong> when you enable auto-apply, we record each
            preview or live submission attempt (including an opt-in consent stamp) in an application
            log tied to your account.
          </li>
          <li>
            <strong>Inbox data (optional):</strong> when you connect a mailbox, message metadata and
            content needed to classify recruiter email and draft replies.
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
          <li>
            Submit job applications on your behalf when you enable auto-apply for a source (using
            your application profile and any site credentials you linked).
          </li>
          <li>
            Power the jobs feed, RSS export, and optional AI features you enable (match summaries,
            cover letters, resume curation, email classification, and reply drafting).
          </li>
          <li>Maintain your account, enforce access controls, and improve reliability.</li>
        </ul>
        <p>We do not sell your personal data. We do not use your data for advertising profiles.</p>
      </section>

      <section>
        <h2>Lawful basis</h2>
        <p>
          We process account, configuration, and operational data to provide the service you request
          (performance of a contract). Optional features that send your personal data to third
          parties — including auto-apply to career sites and AI-backed features — run only after you
          opt in. For those features the lawful basis is your consent, which you can withdraw by
          turning the feature off (for example disabling auto-apply on a source) or deleting your
          account.
        </p>
      </section>

      <section>
        <h2>Third parties and subprocessors</h2>
        <p>
          Depending on how you configure HeadStart, data may be sent to third-party service
          providers that help us operate the product. See our{" "}
          <Link to="/subprocessors">Subprocessors</Link> page for the current list, purposes, and
          safeguards (including DPAs where applicable).
        </p>
        <p>Depending on how you configure HeadStart, data may also be sent to:</p>
        <ul>
          <li>
            <strong>Job boards and career sites</strong> you ask us to monitor (for scraping). When
            you enable auto-apply on a source, we also transmit application-profile data — such as
            your name, email, phone, links, resume file or text, work history, education, skills,
            and custom answers — to that employer&apos;s career site or applicant-tracking system so
            we can submit an application on your behalf. Each live or preview attempt stores an
            auditable consent record on the application log.
          </li>
          <li>
            <strong>Notification providers</strong> you choose (for example ntfy, email via SMTP,
            Slack, Discord, Telegram, or a custom webhook URL).
          </li>
          <li>
            <strong>AI providers</strong> when you enable an AI-backed feature (for example OpenAI,
            Anthropic, or Google Gemini). What we send depends on the purpose:
            <ul>
              <li>
                <strong>Match summaries:</strong> job title, company, location, and search filter
                context for a short &quot;why this matches&quot; blurb.
              </li>
              <li>
                <strong>Cover letters and resume curation:</strong> job posting context plus
                application-profile fields such as name, contact details, skills, work history,
                education, and resume text excerpts.
              </li>
              <li>
                <strong>Email classification:</strong> inbound recruiter message metadata and body
                (and linked application context when available).
              </li>
              <li>
                <strong>Reply drafting:</strong> the recruiter&apos;s message plus profile contact
                details, skills, and custom answers needed to draft a reply you can review.
              </li>
            </ul>
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
          HeadStart uses an httpOnly refresh-token cookie to keep you signed in between visits. This
          cookie is strictly necessary for the service and is set when you log in, independent of
          the consent banner.
        </p>
        <p>
          The short-lived access token is kept in browser memory, not localStorage. Your cookie
          consent choice is stored in <code>localStorage</code> under{" "}
          <code>headstart.cookieConsent</code> so we can remember whether you allowed optional
          cookies. You can change your choice any time via <strong>Cookie settings</strong> in the
          site footer.
        </p>
        <ul>
          <li>
            <strong>Essential only:</strong> only strictly necessary cookies (session sign-in). No
            optional advertising or analytics cookies are loaded.
          </li>
          <li>
            <strong>Accept all:</strong> permits optional cookies when we introduce features such as
            free-tier advertising or usage analytics. As of this policy date, those optional cookies
            are not yet enabled in the product.
          </li>
        </ul>
        <p>We do not sell your personal data or use your data for advertising profiles.</p>
      </section>

      <section>
        <h2>Retention</h2>
        <p>
          We retain account and configuration data while your account is active. Job postings and
          delivery history are kept to power your feed and diagnostics. When you delete resources in
          the app, associated rows are removed from our database. You can export all of your data or
          permanently delete your account from <strong>Settings → Your account</strong> in the app.
        </p>
        <p>
          After account deletion we keep a minimal audit record that a deletion occurred (timestamp
          and a one-way pseudonym of the former email address). That record does not retain your
          plaintext email, IP address, or user agent. Export audit rows for an active account may
          include email and request metadata until you delete the account, at which point they are
          redacted the same way.
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
