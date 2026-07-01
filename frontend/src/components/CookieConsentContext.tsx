/** Cookie consent state shared by the banner and footer settings link. */

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { getCookieConsent, setCookieConsent, type CookieConsentChoice } from "../lib/cookieConsent";
import { CookieConsentBanner } from "./CookieConsentBanner";

type CookieConsentContextValue = {
  choice: CookieConsentChoice | null;
  visible: boolean;
  setChoice: (choice: CookieConsentChoice) => void;
  openCookieSettings: () => void;
};

const CookieConsentContext = createContext<CookieConsentContextValue | null>(null);

export function CookieConsentProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<CookieConsentChoice | null>(() => getCookieConsent());
  const [settingsOpen, setSettingsOpen] = useState(false);

  const setChoice = useCallback((next: CookieConsentChoice) => {
    setCookieConsent(next);
    setChoiceState(next);
    setSettingsOpen(false);
  }, []);

  const openCookieSettings = useCallback(() => {
    setSettingsOpen(true);
  }, []);

  const visible = choice === null || settingsOpen;

  const value = useMemo(
    () => ({ choice, visible, setChoice, openCookieSettings }),
    [choice, visible, setChoice, openCookieSettings],
  );

  return (
    <CookieConsentContext.Provider value={value}>
      {children}
      <CookieConsentBanner />
    </CookieConsentContext.Provider>
  );
}

export function useCookieConsent(): CookieConsentContextValue {
  const ctx = useContext(CookieConsentContext);
  if (!ctx) {
    throw new Error("useCookieConsent must be used within CookieConsentProvider");
  }
  return ctx;
}
