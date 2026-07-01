/** Public subprocessor list and DPA overview for HeadStart. */

import { Link } from "react-router-dom";
import { LegalPageLayout } from "../components/LegalPageLayout";

const EFFECTIVE_DATE = "June 29, 2026";

const SUBPROCESSORS = [
  {
    name: "Amazon Web Services (AWS)",
    purpose: "Cloud hosting, database, cache, and background workers for the HeadStart deployment.",
    data: "Account data, configuration, encrypted credentials and profiles, job history, and operational logs.",
    location: "Region configured by the operator (commonly EU or US).",
    safeguards:
      "AWS Data Processing Addendum (DPA) with Standard Contractual Clauses where required.",
    link: "https://aws.amazon.com/compliance/gdpr-center/",
  },
  {
    name: "Stripe",
    purpose:
      "Subscription billing, checkout, invoices, and payment lifecycle when billing is enabled.",
    data: "Email address, plan, subscription status, Stripe customer and subscription identifiers.",
    location: "United States and other Stripe processing regions.",
    safeguards: "Stripe Data Processing Agreement and SCCs for international transfers.",
    link: "https://stripe.com/legal/dpa",
  },
  {
    name: "OpenAI",
    purpose:
      "Optional AI summaries explaining why a job matches your filters (when the operator enables the OpenAI provider).",
    data: "Job title, company, location, and filter context — never your password or encrypted credentials.",
    location: "United States.",
    safeguards: "OpenAI Data Processing Addendum available to business customers.",
    link: "https://openai.com/policies/data-processing-addendum",
  },
  {
    name: "SMTP email provider",
    purpose:
      "Transactional email such as password reset messages when SMTP is configured on the deployment.",
    data: "Recipient email address and message content required to deliver the email.",
    location: "Depends on the operator's chosen SMTP provider.",
    safeguards:
      "The operator should use a provider with a GDPR-ready DPA (for example SendGrid, Postmark, or Amazon SES).",
    link: null,
  },
] as const;

export function SubprocessorsPage() {
  return (
    <LegalPageLayout title="Subprocessors" effectiveDate={EFFECTIVE_DATE}>
      <p>
        HeadStart (&quot;we&quot;, &quot;us&quot;) uses the third-party service providers below to
        operate a hosted deployment. They process personal data on our behalf as{" "}
        <strong>subprocessors</strong> under Article 28 GDPR. This page supplements our{" "}
        <Link to="/privacy">Privacy Policy</Link>.
      </p>

      <section>
        <h2>Data Processing Agreement (DPA)</h2>
        <p>
          Enterprise customers and EU-based operators may request a Data Processing Agreement that
          describes our role as processor (or joint controller, where applicable), lists
          subprocessors, and documents technical and organizational measures. Contact the
          administrator of the HeadStart instance you use.
        </p>
        <p>
          When you configure notification channels (email, Slack, Discord, Telegram, ntfy, or a
          custom webhook), those destinations are chosen by <strong>you</strong> and are not
          HeadStart subprocessors unless we operate them on your behalf.
        </p>
      </section>

      <section>
        <h2>Current subprocessors</h2>
        <p className="muted">
          The table reflects a typical self-hosted or AWS deployment. Your operator may disable
          billing or AI summaries, which removes Stripe or OpenAI from the active subprocessor list
          for that instance.
        </p>
        <div className="table-scroll">
          <table className="table legal-table">
            <thead>
              <tr>
                <th>Provider</th>
                <th>Purpose</th>
                <th>Data processed</th>
                <th>Location</th>
                <th>Safeguards</th>
              </tr>
            </thead>
            <tbody>
              {SUBPROCESSORS.map((row) => (
                <tr key={row.name}>
                  <td>
                    {row.link ? (
                      <a href={row.link} target="_blank" rel="noreferrer">
                        {row.name}
                      </a>
                    ) : (
                      row.name
                    )}
                  </td>
                  <td>{row.purpose}</td>
                  <td>{row.data}</td>
                  <td>{row.location}</td>
                  <td>{row.safeguards}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2>Changes</h2>
        <p>
          We will update this page when we add or replace subprocessors that materially affect how
          personal data is processed. Material changes will be reflected here with a new effective
          date.
        </p>
      </section>

      <section>
        <h2>Your rights</h2>
        <p>
          You can export or delete your account data from <strong>Settings → Your account</strong>{" "}
          in the app. Successful export and deletion requests are recorded in an audit log visible
          to deployment administrators.
        </p>
      </section>
    </LegalPageLayout>
  );
}
