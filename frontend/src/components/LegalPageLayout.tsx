/** Shared shell for public legal documents (privacy, terms). */

import type { ReactNode } from "react";
import { Brand } from "./Brand";
import { PublicFooter } from "./PublicFooter";

export function LegalPageLayout({
  title,
  effectiveDate,
  children,
}: {
  title: string;
  effectiveDate: string;
  children: ReactNode;
}) {
  return (
    <div className="legal-page">
      <header className="legal-header">
        <Brand className="landing-brand" />
      </header>

      <main className="legal-main">
        <article className="legal-article">
          <header className="legal-article-header">
            <h1>{title}</h1>
            <p className="legal-effective">Effective {effectiveDate}</p>
          </header>
          {children}
        </article>
      </main>

      <PublicFooter />
    </div>
  );
}
