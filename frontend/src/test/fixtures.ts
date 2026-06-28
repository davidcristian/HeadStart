/** Sample API payloads for frontend smoke tests. */

import type { Job, Meta, NotificationTarget, Search, Source } from "../types";

export const sampleMeta: Meta = {
  scrapers: ["greenhouse", "generic_html", "playwright"],
  notifiers: ["ntfy"],
};

export const sampleSource: Source = {
  id: 1,
  name: "ACME Careers",
  adapter_key: "greenhouse",
  base_url: "https://boards.greenhouse.io/acme",
  default_config: { board_token: "acme" },
  enabled: true,
  created_at: "2026-06-28T00:00:00Z",
};

export const sampleTarget: NotificationTarget = {
  id: 10,
  name: "My phone",
  type: "ntfy",
  config: { server_url: "https://ntfy.sh", topic: "jobs", priority: "default" },
  created_at: "2026-06-28T00:00:00Z",
};

export const sampleSearch: Search = {
  id: 20,
  name: "Google SWE",
  source_id: sampleSource.id,
  target_id: sampleTarget.id,
  query_url: "https://example.test/jobs",
  filters: { keywords: "engineer" },
  config: {},
  interval_seconds: 900,
  enabled: true,
  last_run_at: "2026-06-28T12:00:00Z",
  last_error: null,
  next_run_at: "2026-06-28T12:15:00Z",
  created_at: "2026-06-28T00:00:00Z",
  recent_delivery_failures: [],
};

export const sampleJob: Job = {
  id: 100,
  search_id: sampleSearch.id,
  external_id: "job-1",
  title: "Software Engineer",
  company: "ACME",
  location: "Remote",
  url: "https://example.test/jobs/1",
  first_seen_at: "2026-06-28T12:00:00Z",
};
