/** React Query write hooks. Each mutation invalidates the caches it affects so
 * the UI re-fetches authoritative data instead of mutating local state by hand.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type {
  CredentialCreate,
  PlanId,
  PortalSearchRequest,
  PortalSubscribeRequest,
  ProfileData,
  SearchCreate,
  SourceCreate,
  TargetCreate,
} from "../types";
import { invalidate } from "./mutationUtils";
import { queryKeys } from "./queries";

export {
  useApplyToJob,
  useGenerateCoverLetter,
  useGenerateResume,
  useUpdateJob,
} from "./jobMutations";

export function useCreateSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: SourceCreate) => api.createSource(data),
    onSuccess: () => {
      invalidate(qc, queryKeys.sources);
      invalidate(qc, queryKeys.meta);
    },
  });
}

export function useUpdateSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<SourceCreate> }) =>
      api.updateSource(id, data),
    onSuccess: () => invalidate(qc, queryKeys.sources),
  });
}

export function useDeleteSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteSource(id),
    onSuccess: () => {
      invalidate(qc, queryKeys.sources);
      invalidate(qc, queryKeys.meta);
    },
  });
}

export function useTestSource() {
  return useMutation({ mutationFn: (id: number) => api.testSource(id) });
}

export function useCreateSearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: SearchCreate) => api.createSearch(data),
    onSuccess: () => {
      invalidate(qc, queryKeys.searches);
      invalidate(qc, queryKeys.meta);
    },
  });
}

export function useUpdateSearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<SearchCreate> }) =>
      api.updateSearch(id, data),
    onSuccess: () => invalidate(qc, queryKeys.searches),
  });
}

export function useDeleteSearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteSearch(id),
    onSuccess: () => {
      invalidate(qc, queryKeys.searches);
      invalidate(qc, queryKeys.meta);
    },
  });
}

export function useRunSearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.runSearch(id),
    onSuccess: () => invalidate(qc, queryKeys.searches),
  });
}

export function useCreateTarget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: TargetCreate) => api.createTarget(data),
    onSuccess: () => {
      invalidate(qc, queryKeys.targets);
      invalidate(qc, queryKeys.meta);
    },
  });
}

export function useDeleteTarget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteTarget(id),
    onSuccess: () => {
      invalidate(qc, queryKeys.targets);
      invalidate(qc, queryKeys.meta);
    },
  });
}

export function useTestTarget() {
  return useMutation({ mutationFn: (id: number) => api.testTarget(id) });
}

export function useCreateCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CredentialCreate) => api.createCredential(data),
    onSuccess: () => invalidate(qc, queryKeys.credentials),
  });
}

export function useUpdateCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<CredentialCreate> }) =>
      api.updateCredential(id, data),
    onSuccess: () => invalidate(qc, queryKeys.credentials),
  });
}

export function useDeleteCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteCredential(id),
    onSuccess: () => invalidate(qc, queryKeys.credentials),
  });
}

export function useSaveProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ProfileData) => api.saveProfile(data),
    onSuccess: () => invalidate(qc, queryKeys.profile),
  });
}

export function useDeleteProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.deleteProfile(),
    onSuccess: () => invalidate(qc, queryKeys.profile),
  });
}

export function useUploadResume() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.uploadResume(file),
    onSuccess: () => invalidate(qc, queryKeys.profile),
  });
}

export function useDeleteResume() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.deleteResume(),
    onSuccess: () => invalidate(qc, queryKeys.profile),
  });
}

export function useUploadResumeTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.uploadResumeTemplate(file),
    onSuccess: () => invalidate(qc, queryKeys.profile),
  });
}

export function useDeleteResumeTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.deleteResumeTemplate(),
    onSuccess: () => invalidate(qc, queryKeys.profile),
  });
}

export function useRotateFeedUrl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.rotateFeedUrl(),
    onSuccess: () => invalidate(qc, queryKeys.feedUrl),
  });
}

export function useUpdateAdminUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<{ is_active: boolean; is_admin: boolean; plan: PlanId }>;
    }) => api.updateAdminUser(id, patch),
    onSuccess: () => {
      invalidate(qc, queryKeys.adminUsers);
      invalidate(qc, queryKeys.meta);
    },
  });
}

export function useSearchPortals() {
  return useMutation({ mutationFn: (data: PortalSearchRequest) => api.searchPortals(data) });
}

export function useSubscribePortals() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: PortalSubscribeRequest) => api.subscribePortals(data),
    onSuccess: () => {
      invalidate(qc, queryKeys.sources);
      invalidate(qc, queryKeys.searches);
      // Prefix key so every category/query-filtered portals cache refetches, not
      // just the unfiltered ["portals", null, null] one.
      invalidate(qc, ["portals"]);
      invalidate(qc, queryKeys.meta);
    },
  });
}

export function useDraftInboxReply() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      classification_id?: number;
      message_uid?: number;
      regenerate?: boolean;
    }) => api.draftInboxReply(data),
    onSuccess: () => {
      // Prefix key so every stage-filtered pipeline cache refetches, not just the
      // unfiltered ["applications", null] one.
      invalidate(qc, ["applications"]);
    },
  });
}
