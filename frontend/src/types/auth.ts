import type { PlanId } from "./meta";

export interface User {
  id: number;
  email: string;
  is_admin: boolean;
  is_active: boolean;
  plan: PlanId;
  onboarding_completed_at: string | null;
  email_verified_at: string | null;
  /** Preferred notification/auth email locale; null inherits DEFAULT_LOCALE. */
  locale?: "en" | "de" | null;
  created_at: string;
}

export type AdminUser = User;

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
}
