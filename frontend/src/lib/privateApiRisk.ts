/** LinkedIn/Indeed cookie automation ToS / account-ban risk (APL-17 / XCT-19). */

export const PRIVATE_API_RISK_ADAPTERS = new Set(["linkedin", "indeed"]);

export const PRIVATE_API_APPLY_RISK_CONFIRM =
  "LinkedIn/Indeed hosted Easy Apply uses private APIs (Voyager / smartapply) with your " +
  "session cookies. Automated use can violate their Terms of Service and risk account " +
  "suspension or bans. Enable only if you accept this risk?";

export const PRIVATE_API_CREDENTIAL_RISK_CONFIRM =
  "LinkedIn/Indeed session cookies let HeadStart scrape (and optionally auto-apply) as you. " +
  "Automated access typically violates those platforms' Terms of Service and can risk " +
  "account suspension, bans, or legal exposure. Save only if you accept this risk?";

/** True when the adapter injects member session cookies into LinkedIn/Indeed. */
export function isPrivateApiRiskAdapter(adapterKey: string): boolean {
  return PRIVATE_API_RISK_ADAPTERS.has(adapterKey);
}
