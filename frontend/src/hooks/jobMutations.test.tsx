import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import type { MockInstance } from "vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  updateJob: vi.fn(async () => ({ id: 1 })),
  applyToJob: vi.fn(async () => ({ status: "queued" })),
  generateCoverLetter: vi.fn(async () => ({ cover_letter: "hi" })),
  generateResume: vi.fn(async () => ({ pdf_b64: "x" })),
}));
vi.mock("../api", () => ({ api }));

import {
  useApplyToJob,
  useGenerateCoverLetter,
  useGenerateResume,
  useUpdateJob,
} from "./jobMutations";

let client: QueryClient;
let invalidateSpy: MockInstance<QueryClient["invalidateQueries"]>;

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function invalidatedKeys(): unknown[] {
  return invalidateSpy.mock.calls.map((c) => (c[0] as { queryKey: unknown }).queryKey);
}

beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockClear());
  api.applyToJob.mockResolvedValue({ status: "queued" });
  client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  invalidateSpy = vi.spyOn(client, "invalidateQueries").mockResolvedValue();
});

describe("useUpdateJob", () => {
  it("updates the job and invalidates the jobs cache", async () => {
    const { result } = renderHook(() => useUpdateJob(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ id: 1, status: "applied" });
    });
    expect(api.updateJob).toHaveBeenCalledWith(1, { status: "applied" });
    expect(invalidatedKeys()).toContainEqual(["jobs"]);
  });
});

describe("useApplyToJob", () => {
  it("live apply invalidates logs and the applications pipeline", async () => {
    const { result } = renderHook(() => useApplyToJob(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ id: 1 });
    });
    expect(api.applyToJob).toHaveBeenCalledWith(1, {
      dry_run: false,
      cover_letter: undefined,
      tailored_resume_b64: undefined,
      tailored_resume_artifact_id: undefined,
    });
    const keys = invalidatedKeys();
    expect(keys).toContainEqual(["application-logs"]);
    expect(keys).toContainEqual(["applications"]);
  });

  it("dry-run apply does not touch the applications pipeline", async () => {
    const { result } = renderHook(() => useApplyToJob(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ id: 1, dry_run: true });
    });
    const keys = invalidatedKeys();
    expect(keys).toContainEqual(["application-logs"]);
    expect(keys).not.toContainEqual(["applications"]);
    expect(keys).not.toContainEqual(["jobs"]);
  });

  it("a submitted result also invalidates the jobs cache", async () => {
    api.applyToJob.mockResolvedValueOnce({ status: "submitted" });
    const { result } = renderHook(() => useApplyToJob(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ id: 1 });
    });
    expect(invalidatedKeys()).toContainEqual(["jobs"]);
  });
});

describe("generation hooks", () => {
  it("useGenerateCoverLetter calls the api", async () => {
    const { result } = renderHook(() => useGenerateCoverLetter(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync(5);
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.generateCoverLetter).toHaveBeenCalledWith(5);
  });

  it("useGenerateResume calls the api", async () => {
    const { result } = renderHook(() => useGenerateResume(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync(5);
    });
    expect(api.generateResume).toHaveBeenCalledWith(5);
  });
});
