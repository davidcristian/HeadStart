/** Types mirroring the backend Pydantic schemas (see backend/app/schemas). */

export type Json = Record<string, unknown>;

export interface Source {
  id: number;
  name: string;
  adapter_key: string;
  base_url: string;
  default_config: Json;
  enabled: boolean;
  created_at: string;
}

export type SourceCreate = Omit<Source, "id" | "created_at">;

export interface Search {
  id: number;
  name: string;
  source_id: number;
  target_id: number | null;
  query_url: string;
  filters: Json;
  config: Json;
  interval_seconds: number;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string;
  created_at: string;
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
  | "enabled"
>;

export interface NotificationTarget {
  id: number;
  name: string;
  type: string;
  config: Json;
  created_at: string;
}

export type TargetCreate = Omit<NotificationTarget, "id" | "created_at">;

export interface Job {
  id: number;
  search_id: number;
  external_id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  first_seen_at: string;
}

export interface Meta {
  scrapers: string[];
  notifiers: string[];
}

export interface Health {
  status: string;
  version: string;
  environment: string;
}

export interface User {
  id: number;
  email: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface SiteCredential {
  id: number;
  source_id: number;
  name: string;
  enabled: boolean;
  created_at: string;
  has_cookies: boolean;
  has_headers: boolean;
  has_session: boolean;
}

export interface CredentialCreate {
  source_id: number;
  name: string;
  enabled: boolean;
  cookies: Record<string, string>;
  headers: Record<string, string>;
  session: Record<string, string>;
}
