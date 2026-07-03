import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ApplicationLog } from "../types";

const getApplicationLog = vi.hoisted(() => vi.fn());
vi.mock("./index", () => ({ api: { getApplicationLog } }));

import { pollApplicationLog } from "./pollApplicationLog";

function log(status: string): ApplicationLog {
  return { id: 1, status } as unknown as ApplicationLog;
}

beforeEach(() => {
  vi.useFakeTimers();
  getApplicationLog.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("pollApplicationLog", () => {
  it("returns immediately when the first poll is already terminal", async () => {
    getApplicationLog.mockResolvedValueOnce(log("submitted"));
    await expect(pollApplicationLog(1)).resolves.toEqual(log("submitted"));
    expect(getApplicationLog).toHaveBeenCalledTimes(1);
  });

  it("keeps polling until a terminal status appears", async () => {
    getApplicationLog
      .mockResolvedValueOnce(log("queued"))
      .mockResolvedValueOnce(log("in_progress"))
      .mockResolvedValueOnce(log("failed"));
    const promise = pollApplicationLog(1);
    await vi.advanceTimersByTimeAsync(2000);
    await expect(promise).resolves.toEqual(log("failed"));
    expect(getApplicationLog).toHaveBeenCalledTimes(3);
  });

  it("treats dry_run as terminal", async () => {
    getApplicationLog.mockResolvedValueOnce(log("dry_run"));
    await expect(pollApplicationLog(1)).resolves.toEqual(log("dry_run"));
  });

  it("throws once the poll timeout elapses without a terminal status", async () => {
    getApplicationLog.mockResolvedValue(log("queued"));
    const promise = pollApplicationLog(1);
    const assertion = expect(promise).rejects.toThrow(/still processing/);
    await vi.advanceTimersByTimeAsync(5 * 60 * 1000 + 1000);
    await assertion;
  });
});
