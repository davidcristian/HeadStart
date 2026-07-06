import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DocumentGeneration } from "../types";

const getDocumentGeneration = vi.hoisted(() => vi.fn());
vi.mock("./index", () => ({ api: { getDocumentGeneration } }));

import { pollDocumentGeneration } from "./pollDocumentGeneration";

function generation(status: DocumentGeneration["status"]): DocumentGeneration {
  return {
    id: 1,
    kind: "resume",
    status,
    error: null,
    result: null,
    created_at: "2026-07-10T00:00:00Z",
    updated_at: "2026-07-10T00:00:00Z",
  };
}

beforeEach(() => {
  vi.useFakeTimers();
  getDocumentGeneration.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("pollDocumentGeneration", () => {
  it("returns immediately when the first poll is already terminal", async () => {
    getDocumentGeneration.mockResolvedValueOnce(generation("ready"));
    await expect(pollDocumentGeneration(1)).resolves.toEqual(generation("ready"));
    expect(getDocumentGeneration).toHaveBeenCalledTimes(1);
  });

  it("keeps polling until a terminal status appears", async () => {
    getDocumentGeneration
      .mockResolvedValueOnce(generation("queued"))
      .mockResolvedValueOnce(generation("processing"))
      .mockResolvedValueOnce(generation("failed"));
    const promise = pollDocumentGeneration(1);
    await vi.advanceTimersByTimeAsync(2000);
    await expect(promise).resolves.toEqual(generation("failed"));
    expect(getDocumentGeneration).toHaveBeenCalledTimes(3);
  });

  it("throws once the poll timeout elapses without a terminal status", async () => {
    getDocumentGeneration.mockResolvedValue(generation("queued"));
    const promise = pollDocumentGeneration(1);
    const assertion = expect(promise).rejects.toThrow(/still processing/);
    await vi.advanceTimersByTimeAsync(5 * 60 * 1000 + 1000);
    await assertion;
  });
});
