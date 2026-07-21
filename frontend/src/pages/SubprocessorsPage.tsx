/** Public subprocessor list and DPA overview for HeadStart. */

import { Link } from "react-router-dom";
import { LegalPageLayout } from "../components/LegalPageLayout";

const EFFECTIVE_DATE = "July 4, 2026";

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
      "Optional AI features (match summaries, cover letters, resume curation, email classification, reply drafting) when the operator enables the OpenAI provider.",
    data: "Job and filter context, application-profile fields, resume text excerpts, and recruiter message content depending on the enabled purpose. We never send your password or encrypted credentials.",
    location: "United States.",
    safeguards: "OpenAI Data Processing Addendum available to business customers.",
    link: "https://openai.com/policies/data-processing-addendum",
  },
  {
    name: "Google (Gemini)",
    purpose:
      "Optional AI features (match summaries, cover letters, resume curation, email classification, reply drafting) when the operator enables the Gemini provider.",
    data: "Job and filter context, application-profile fields, resume text excerpts, and recruiter message content depending on the enabled purpose. We never send your password or encrypted credentials.",
    location: "United States and other Google Cloud processing regions.",
    safeguards: "Google Cloud Data Processing Addendum and SCCs where required.",
    link: "https://cloud.google.com/terms/data-processing-addendum",
  },
  {
    name: "Anthropic",
    purpose:
      "Optional AI features (match summaries, cover letters, resume curation, email classification, reply drafting) when the operator enables the Anthropic provider.",
    data: "Job and filter context, application-profile fields, resume text excerpts, and recruiter message content depending on the enabled purpose. We never send your password or encrypted credentials.",
    location: "United States.",
    safeguards: "Anthropic Data Processing Addendum available to business customers.",
    link: "https://www.anthropic.com/legal/commercial-terms",
  },
  {
    name: "Google (Gmail)",
    purpose:
      "Optional inbox mailbox OAuth when a user connects Gmail for the application agent (dev inbox).",
    data: "OAuth tokens, connected mailbox address, and message metadata/body processed for classification and reply drafting.",
    location: "United States and other Google processing regions.",
    safeguards: "Google API Services User Data Policy and Google Cloud DPA where applicable.",
    link: "https://developers.google.com/terms/api-services-user-data-policy",
  },
  {
    name: "Microsoft (Outlook)",
    purpose:
      "Optional inbox mailbox OAuth when a user connects Outlook / Microsoft 365 for the application agent (dev inbox).",
    data: "OAuth tokens, connected mailbox address, and message metadata/body processed for classification and reply drafting.",
    location: "Microsoft Azure regions configured for the tenant.",
    safeguards: "Microsoft Products and Services Data Protection Addendum (DPA).",
    link: "https://www.microsoft.com/licensing/docs/view/Microsoft-Products-and-Services-Data-Protection-Addendum-DPA",
  },
  {
    name: "Yahoo",
    purpose:
      "Optional inbox mailbox OAuth when a user connects Yahoo Mail for the application agent (dev inbox).",
    data: "OAuth tokens, connected mailbox address, and message metadata/body processed for classification and reply drafting.",
    location: "United States and other Yahoo processing regions.",
    safeguards:
      "The operator should confirm Yahoo's applicable privacy terms and DPA coverage before enabling Yahoo OAuth in production.",
    link: "https://legal.yahoo.com/us/en/yahoo/privacy/index.html",
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
          billing, AI providers, or inbox mailbox OAuth, which removes Stripe, OpenAI / Gemini /
          Anthropic, or Gmail / Outlook / Yahoo from the active subprocessor list for that instance.
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
