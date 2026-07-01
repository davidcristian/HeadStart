import type { Json } from "./json";

export interface Source {
  id: number;
  name: string;
  adapter_key: string;
  base_url: string;
  default_config: Json;
  enabled: boolean;
  auto_apply_enabled: boolean;
  created_at: string;
}

export type SourceCreate = Omit<Source, "id" | "created_at" | "auto_apply_enabled"> & {
  auto_apply_enabled?: boolean;
};

export interface SourceDetectResult {
  adapter_key: string;
  suggested_name: string;
  base_url: string;
  default_config: Json;
  query_url: string;
}

export interface JobPostingPreview {
  external_id: string;
  title: string;
  company: string;
  location: string;
  url: string;
}

export interface SourceTestResult {
  ok: boolean;
  found: number;
  sample: JobPostingPreview[];
  error: string | null;
}
