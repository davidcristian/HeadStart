export type PlanId = "free" | "starter" | "plus" | "pro";

export interface PlanLimits {
  max_searches: number;
  max_sources: number;
  max_targets: number;
}

export interface PlanUsage {
  searches: number;
  sources: number;
  targets: number;
}

export interface PlanFeatures {
  digest_mode: boolean;
  ai_summaries: boolean;
  site_credentials: boolean;
  rss_feed: boolean;
  portal_search: boolean;
}

export interface AccountPlan {
  plan: PlanId;
  effective_plan: PlanId;
  unlimited: boolean;
  show_ads: boolean;
  limits: PlanLimits;
  usage: PlanUsage;
  features: PlanFeatures;
  allowed_scrapers: string[];
  allowed_notifiers: string[];
}

export interface AdsConfig {
  external_slot_url: string | null;
}

export interface Meta {
  scrapers: string[];
  notifiers: string[];
  appliers: string[];
  mailboxes: string[];
  inbox_agent_enabled: boolean;
  plan: AccountPlan;
  ads: AdsConfig;
}

export interface Health {
  status: string;
  version: string;
  environment: string;
}
