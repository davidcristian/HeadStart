/** Persist the visitor's cookie consent choice in localStorage (not a cookie). */

export type CookieConsentChoice = "essential" | "all";

const STORAGE_KEY = "headstart.cookieConsent";

export function getCookieConsent(): CookieConsentChoice | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw === "essential" || raw === "all") return raw;
  return null;
}

export function setCookieConsent(choice: CookieConsentChoice): void {
  localStorage.setItem(STORAGE_KEY, choice);
}

export function clearCookieConsent(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function hasCookieConsent(): boolean {
  return getCookieConsent() !== null;
}

/** Whether optional cookies (e.g. future ads or analytics) may be loaded. */
export function acceptsOptionalCookies(): boolean {
  return getCookieConsent() === "all";
}
