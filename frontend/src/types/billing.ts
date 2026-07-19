import type { PlanId } from "./meta";

export type BillingPeriod = "monthly" | "annual";

export interface BillingStatus {
  configured: boolean;
  plan: PlanId;
  subscription_status: string | null;
  has_stripe_subscription: boolean;
  can_checkout: boolean;
  can_manage: boolean;
  trial_days: number;
  /** ISO 4217 lowercase; mirrors backend BILLING_CURRENCY (FRO-35). */
  currency: string;
}

export type PromoType = "percent_off" | "fixed_amount" | "free_trial_days" | "plan_upgrade";

export interface PromoValidation {
  code: string;
  promo_type: PromoType;
  description: string;
  trial_days: number | null;
  percent_off: number | null;
  amount_off_cents: number | null;
  plan_target: PlanId | null;
}

export interface PromoCode {
  id: number;
  code: string;
  promo_type: PromoType;
  value_int: number;
  plan_target: PlanId | null;
  max_redemptions: number | null;
  redemption_count: number;
  expires_at: string | null;
  active: boolean;
  one_per_user: boolean;
  eligible_plans: PlanId[] | null;
  stripe_coupon_id: string | null;
  stripe_promotion_code_id: string | null;
  created_at: string;
}

export interface PromoRedemption {
  id: number;
  promo_code_id: number;
  user_id: number;
  stripe_checkout_session_id: string | null;
  created_at: string;
}
