export interface AdminSearchError {
  search_id: number;
  search_name: string;
  user_email: string;
  last_error: string;
  last_run_at: string | null;
}

export interface AdminStats {
  users_total: number;
  users_active: number;
  searches_total: number;
  searches_enabled: number;
  searches_with_error: number;
  sources_total: number;
  seen_jobs_total: number;
  deliveries_sent: number;
  deliveries_failed: number;
  recent_errors: AdminSearchError[];
}

export interface DataRequestLog {
  id: number;
  user_id: number | null;
  user_email: string;
  request_type: "export" | "delete";
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}
