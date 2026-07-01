/** Wrap public pages in providers required by shared chrome (footer, consent). */

import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { CookieConsentProvider } from "../components/CookieConsentContext";

export function renderPublicPage(ui: ReactElement) {
  return (
    <MemoryRouter>
      <CookieConsentProvider>{ui}</CookieConsentProvider>
    </MemoryRouter>
  );
}
