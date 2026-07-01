import type { PlanId } from "./meta";

export interface User {
  id: number;
  email: string;
  is_admin: boolean;
  is_active: boolean;
  plan: PlanId;
  onboarding_completed_at: string | null;
  created_at: string;
}

export type AdminUser = User;

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
}
