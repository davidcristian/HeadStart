/** Public Impressum (German legal notice) for HeadStart — placeholder until operator details are set. */

import { Link } from "react-router-dom";
import { LegalPageLayout } from "../components/LegalPageLayout";

const EFFECTIVE_DATE = "19. Juli 2026";

export function ImpressumPage() {
  return (
    <LegalPageLayout title="Impressum" effectiveDate={EFFECTIVE_DATE} effectiveLabel="Stand">
      <p>
        Angaben gemäß § 5 TMG und § 18 Abs. 2 MStV. Die folgenden Platzhalter müssen vom Betreiber
        dieser HeadStart-Instanz durch die tatsächlichen Unternehmens- und Kontaktdaten ersetzt
        werden, bevor die Seite öffentlich in Deutschland genutzt wird.
      </p>

      <section>
        <h2>Diensteanbieter</h2>
        <p>
          <strong>[Firmenname / Name des Betreibers]</strong>
          <br />
          [Straße und Hausnummer]
          <br />
          [PLZ Ort]
          <br />
          Deutschland
        </p>
      </section>

      <section>
        <h2>Kontakt</h2>
        <p>
          E-Mail: <strong>[kontakt@beispiel.de]</strong>
          <br />
          Telefon: <strong>[+49 …]</strong> (optional)
        </p>
      </section>

      <section>
        <h2>Vertretungsberechtigte Person</h2>
        <p>
          Geschäftsführer / Inhaber: <strong>[Name]</strong>
        </p>
      </section>

      <section>
        <h2>Registereintrag</h2>
        <p>
          Registergericht: <strong>[Amtsgericht …]</strong>
          <br />
          Registernummer: <strong>[HRB …]</strong>
        </p>
        <p>
          <em>
            Entfällt bei Einzelunternehmen oder natürlichen Personen ohne Handelsregistereintrag —
            diesen Abschnitt dann entfernen oder als nicht zutreffend kennzeichnen.
          </em>
        </p>
      </section>

      <section>
        <h2>Umsatzsteuer-ID</h2>
        <p>
          Umsatzsteuer-Identifikationsnummer gemäß § 27a UStG: <strong>[DE…]</strong>
        </p>
        <p>
          <em>Nur ausfüllen, wenn eine USt-IdNr. vorliegt; sonst diesen Abschnitt entfernen.</em>
        </p>
      </section>

      <section>
        <h2>Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV</h2>
        <p>
          <strong>[Name]</strong>
          <br />
          [Straße und Hausnummer]
          <br />
          [PLZ Ort]
        </p>
      </section>

      <section>
        <h2>EU-Streitschlichtung</h2>
        <p>
          Die Europäische Kommission stellt eine Plattform zur Online-Streitbeilegung (OS) bereit:{" "}
          <a href="https://ec.europa.eu/consumers/odr/" rel="noopener noreferrer" target="_blank">
            https://ec.europa.eu/consumers/odr/
          </a>
          . Unsere E-Mail-Adresse finden Sie oben im Impressum.
        </p>
      </section>

      <section>
        <h2>Verbraucherstreitbeilegung</h2>
        <p>
          Wir sind nicht verpflichtet und nicht bereit, an Streitbeilegungsverfahren vor einer
          Verbraucherschlichtungsstelle teilzunehmen.
        </p>
      </section>

      <section>
        <h2>Hinweis für Betreiber</h2>
        <p>
          Diese Seite ist eine Vorlage. Ersetzen Sie alle Platzhalter in eckigen Klammern durch Ihre
          gültigen Angaben und entfernen Sie nicht zutreffende Abschnitte. Weitere Informationen zur
          Datenverarbeitung finden Sie in unserer{" "}
          <Link to="/privacy">Datenschutzerklärung (Privacy Policy)</Link>.
        </p>
      </section>
    </LegalPageLayout>
  );
}
