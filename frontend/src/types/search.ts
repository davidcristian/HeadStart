import type { Json } from "./json";

export interface DeliveryFailure {
  job_title: string;
  job_url: string;
  error: string | null;
  sent_at: string;
}

export interface Search {
  id: number;
  name: string;
  source_id: number;
  target_id: number | null;
  query_url: string;
  filters: Json;
  config: Json;
  interval_seconds: number;
  notification_mode: "immediate" | "digest";
  digest_interval_seconds: number;
  enabled: boolean;
  last_run_at: string | null;
  last_digest_at: string | null;
  last_error: string | null;
  next_run_at: string;
  created_at: string;
  recent_delivery_failures: DeliveryFailure[];
}

export type SearchCreate = Pick<
  Search,
  | "name"
  | "source_id"
  | "target_id"
  | "query_url"
  | "filters"
  | "config"
  | "interval_seconds"
  | "notification_mode"
  | "digest_interval_seconds"
  | "enabled"
>;

export type SearchRunStatus = "queued" | "processing" | "ready" | "failed";

export interface SearchRunResult {
  id: number;
  search_id: number;
  status: SearchRunStatus;
  found: number;
  new: number;
  notified: number;
  failed: number;
  skipped: number;
  filtered: number;
  queued: number;
  closed: number;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeedUrl {
  url: string;
  token: string;
}
