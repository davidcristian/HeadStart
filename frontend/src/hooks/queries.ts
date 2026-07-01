/** React Query read hooks + the shared query-key registry.
 *
 * Keeping every key in one place lets mutations (see ./mutations) invalidate the
 * right caches without pages having to know about cache internals.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { JobStatus } from "../types";

export const queryKeys = {
  health: ["health"] as const,
  meta: ["meta"] as const,
  me: ["me"] as const,
  portals: (category?: string, query?: string) => ["portals", category ?? null, query ?? null] as const,
  sources: ["sources"] as const,
  searches: ["searches"] as const,
  targets: ["targets"] as const,
  credentials: ["credentials"] as const,
  profile: ["profile"] as const,
  applicationLogs: ["application-logs"] as const,
  feedUrl: ["feed-url"] as const,
  jobs: (searchId?: number, status?: JobStatus) =>
    ["jobs", searchId ?? null, status ?? null] as const,
  adminUsers: ["admin", "users"] as const,
  adminStats: ["admin", "stats"] as const,
  adminDataRequests: ["admin", "data-requests"] as const,
};

export function useHealth() {
  return useQuery({ queryKey: queryKeys.health, queryFn: () => api.health() });
}

export function useMeta() {
  return useQuery({ queryKey: queryKeys.meta, queryFn: () => api.meta() });
}

export function useMe() {
  return useQuery({ queryKey: queryKeys.me, queryFn: () => api.me() });
}

export function useSources() {
  return useQuery({ queryKey: queryKeys.sources, queryFn: () => api.listSources() });
}

export function usePortals(category?: string, query?: string) {
  return useQuery({
    queryKey: queryKeys.portals(category, query),
    queryFn: () => api.listPortals({ category, q: query }),
  });
}

export function useSearches() {
  return useQuery({ queryKey: queryKeys.searches, queryFn: () => api.listSearches() });
}

export function useTargets() {
  return useQuery({ queryKey: queryKeys.targets, queryFn: () => api.listTargets() });
}

export function useCredentials() {
  return useQuery({ queryKey: queryKeys.credentials, queryFn: () => api.listCredentials() });
}

export function useProfile() {
  return useQuery({ queryKey: queryKeys.profile, queryFn: () => api.getProfile() });
}

export function useApplicationLogs(limit = 100) {
  return useQuery({
    queryKey: [...queryKeys.applicationLogs, limit] as const,
    queryFn: () => api.listApplicationLogs(limit),
  });
}

export function useFeedUrl(enabled = true) {
  return useQuery({
    queryKey: queryKeys.feedUrl,
    queryFn: () => api.getFeedUrl(),
    enabled,
  });
}

export function useJobs(searchId?: number, status?: JobStatus) {
  return useQuery({
    queryKey: queryKeys.jobs(searchId, status),
    queryFn: () => api.listJobs(searchId, status),
  });
}

export function useAdminUsers() {
  return useQuery({ queryKey: queryKeys.adminUsers, queryFn: () => api.listAdminUsers() });
}

export function useAdminStats() {
  return useQuery({ queryKey: queryKeys.adminStats, queryFn: () => api.getAdminStats() });
}

export function useAdminDataRequests(limit = 100) {
  return useQuery({
    queryKey: [...queryKeys.adminDataRequests, limit] as const,
    queryFn: () => api.listAdminDataRequests(limit),
  });
}
