/** Curated employer portal from GET /portals. */

export type PortalCategory = "big_tech" | "unicorn" | "ai";

export type Portal = {
  id: string;
  company_name: string;
  category: PortalCategory;
  adapter_key: string;
  base_url: string;
  default_config: Record<string, unknown>;
  supports_auto_apply: boolean;
  allowed_on_plan: boolean;
  already_added: boolean;
};

export type PortalList = {
  items: Portal[];
  categories: PortalCategory[];
};

export type PortalSearchRequest = {
  keywords: string;
  category?: PortalCategory;
  portal_ids?: string[];
  location?: string;
  workplace?: "remote" | "hybrid" | "onsite";
};

export type PortalJob = {
  portal_id: string;
  company_name: string;
  external_id: string;
  title: string;
  location: string;
  url: string;
};

export type PortalSearchError = {
  portal_id: string;
  company_name: string;
  error: string;
};

export type PortalSearchResult = {
  items: PortalJob[];
  portals_searched: number;
  portals_failed: number;
  errors: PortalSearchError[];
};

export type PortalSubscribeRequest = {
  portal_ids: string[];
  keywords: string;
  target_id: number;
  interval_seconds?: number;
  notification_mode?: "immediate" | "digest";
  digest_interval_seconds?: number;
  location?: string;
  workplace?: "remote" | "hybrid" | "onsite";
};

export type PortalSubscribeResult = {
  sources_created: number;
  searches_created: number;
  search_ids: number[];
  skipped_portal_ids: string[];
  message: string | null;
};
