/** Public terms of use for HeadStart. */

import { LegalPageLayout } from "../components/LegalPageLayout";

const EFFECTIVE_DATE = "June 28, 2026";

export function TermsOfUsePage() {
  return (
    <LegalPageLayout title="Terms of Use" effectiveDate={EFFECTIVE_DATE}>
      <p>
        These Terms of Use (&quot;Terms&quot;) govern your access to HeadStart (&quot;the
        service&quot;). By creating an account or using the service, you agree to these Terms. If
        you do not agree, do not use HeadStart.
      </p>

      <section>
        <h2>The service</h2>
        <p>
          HeadStart monitors job boards and career pages you configure, filters postings against your
          criteria, and sends alerts through channels you choose. We may add, change, or remove
          features over time. The service is provided on an &quot;as is&quot; basis without
          guarantees of uptime, completeness, or fitness for a particular purpose.
        </p>
      </section>

      <section>
        <h2>Eligibility and accounts</h2>
        <p>
          You must be able to form a binding contract in your jurisdiction to use HeadStart. You are
          responsible for your account credentials and for all activity under your account. Notify
          your instance operator promptly if you suspect unauthorized access.
        </p>
      </section>

      <section>
        <h2>Acceptable use</h2>
        <p>You agree not to:</p>
        <ul>
          <li>Use the service for unlawful purposes or to violate third-party terms of service.</li>
          <li>
            Configure aggressive scrape intervals, bypass rate limits, or otherwise impose
            unreasonable load on job boards or our infrastructure.
          </li>
          <li>
            Attempt to access another user&apos;s data, probe or disrupt the service, or introduce
            malware.
          </li>
          <li>
            Misrepresent your identity or submit application materials on behalf of others without
            authorization.
          </li>
        </ul>
        <p>
          Scraping and automated access to third-party sites may be restricted by those sites. You
          are solely responsible for compliance with applicable site policies and laws.
        </p>
      </section>

      <section>
        <h2>Your content and credentials</h2>
        <p>
          You retain ownership of configuration, credentials, profiles, and other data you submit.
          You grant us the rights necessary to store, process, and transmit that data solely to
          operate the service (for example, to run scrapes and send notifications you requested).
        </p>
        <p>
          Do not store credentials or tokens in the service unless you accept the risk that a
          compromise of the deployment could expose them. Rotate secrets when no longer needed.
        </p>
      </section>

      <section>
        <h2>Job listings and notifications</h2>
        <p>
          HeadStart is not an employer, recruiter, or job board. Listings come from external sites;
          we do not verify accuracy, availability, compensation, or eligibility. Alerts may be
          delayed, duplicated, or missed due to site changes, rate limits, or technical failures.
          Always confirm details on the original posting before applying.
        </p>
      </section>

      <section>
        <h2>Auto-apply and future features</h2>
        <p>
          Features that submit applications on your behalf require explicit opt-in where implemented.
          You are responsible for reviewing materials sent in your name and for outcomes of any
          automated submission.
        </p>
      </section>

      <section>
        <h2>Termination</h2>
        <p>
          You may stop using the service at any time. We or your instance operator may suspend or
          terminate access for violations of these Terms, abuse, or operational reasons. Provisions
          that by nature should survive (disclaimers, limitations of liability) continue after
          termination.
        </p>
      </section>

      <section>
        <h2>Disclaimer of warranties</h2>
        <p>
          TO THE MAXIMUM EXTENT PERMITTED BY LAW, THE SERVICE IS PROVIDED WITHOUT WARRANTIES OF ANY
          KIND, WHETHER EXPRESS OR IMPLIED, INCLUDING MERCHANTABILITY, FITNESS FOR A PARTICULAR
          PURPOSE, AND NON-INFRINGEMENT.
        </p>
      </section>

      <section>
        <h2>Limitation of liability</h2>
        <p>
          TO THE MAXIMUM EXTENT PERMITTED BY LAW, HEADSTART OPERATORS AND CONTRIBUTORS WILL NOT BE
          LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR ANY
          LOSS OF PROFITS, DATA, OR GOODWILL, ARISING FROM YOUR USE OF THE SERVICE. OUR AGGREGATE
          LIABILITY FOR DIRECT DAMAGES IS LIMITED TO THE GREATER OF (A) AMOUNTS YOU PAID US FOR THE
          SERVICE IN THE TWELVE MONTHS BEFORE THE CLAIM OR (B) ONE HUNDRED US DOLLARS (US$100).
        </p>
      </section>

      <section>
        <h2>Changes</h2>
        <p>
          We may update these Terms from time to time. Continued use after the effective date of
          revised Terms constitutes acceptance. Material changes will be posted on this page.
        </p>
      </section>

      <section>
        <h2>Contact</h2>
        <p>
          Questions about these Terms? Contact the administrator of the HeadStart deployment you are
          using.
        </p>
      </section>
    </LegalPageLayout>
  );
}
