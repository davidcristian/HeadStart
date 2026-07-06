import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SearchRunResult } from "../types";

const getSearchRun = vi.hoisted(() => vi.fn());
vi.mock("./index", () => ({ api: { getSearchRun } }));

import { pollSearchRun } from "./pollSearchRun";

function run(status: SearchRunResult["status"]): SearchRunResult {
  return {
    id: 1,
    search_id: 20,
    status,
    found: 1,
    new: 1,
    notified: 0,
    failed: 0,
    skipped: 0,
    filtered: 0,
    queued: 0,
    closed: 0,
    error: null,
    created_at: "2026-07-10T00:00:00Z",
    updated_at: "2026-07-10T00:00:00Z",
  };
}

beforeEach(() => {
  getSearchRun.mockReset();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("pollSearchRun", () => {
  it("returns immediately when already terminal", async () => {
    getSearchRun.mockResolvedValueOnce(run("ready"));
    await expect(pollSearchRun(1)).resolves.toEqual(run("ready"));
    expect(getSearchRun).toHaveBeenCalledTimes(1);
  });

  it("polls until ready", async () => {
    getSearchRun
      .mockResolvedValueOnce(run("queued"))
      .mockResolvedValueOnce(run("processing"))
      .mockResolvedValueOnce(run("ready"));
    const promise = pollSearchRun(1);
    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(1000);
    await expect(promise).resolves.toEqual(run("ready"));
    expect(getSearchRun).toHaveBeenCalledTimes(3);
  });

  it("times out while still queued", async () => {
    getSearchRun.mockResolvedValue(run("queued"));
    const promise = pollSearchRun(1);
    const expectation = expect(promise).rejects.toThrow(/still processing/);
    await vi.advanceTimersByTimeAsync(5 * 60 * 1000);
    await expectation;
  });
});
