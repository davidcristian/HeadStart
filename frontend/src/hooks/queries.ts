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
  sources: ["sources"] as const,
  searches: ["searches"] as const,
  targets: ["targets"] as const,
  credentials: ["credentials"] as const,
  profile: ["profile"] as const,
  feedUrl: ["feed-url"] as const,
  jobs: (searchId?: number, status?: JobStatus) =>
    ["jobs", searchId ?? null, status ?? null] as const,
  adminUsers: ["admin", "users"] as const,
  adminStats: ["admin", "stats"] as const,
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
