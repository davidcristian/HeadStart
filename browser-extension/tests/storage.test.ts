import { beforeEach, describe, expect, it, vi } from "vitest";

import { defaultAppBaseUrl, loadSession, saveSession } from "../src/storage";

const store: Record<string, unknown> = {};

beforeEach(() => {
  for (const key of Object.keys(store)) {
    delete store[key];
  }
  vi.stubGlobal("chrome", {
    storage: {
      local: {
        get: vi.fn(async (key: string) => ({ [key]: store[key] })),
        set: vi.fn(async (value: Record<string, unknown>) => {
          Object.assign(store, value);
        }),
        remove: vi.fn(async (key: string) => {
          delete store[key];
        }),
      },
    },
  });
});

describe("session storage", () => {
  it("round-trips a saved session", async () => {
    await saveSession({
      apiBaseUrl: "http://localhost:8000",
      appBaseUrl: defaultAppBaseUrl(),
      accessToken: "access",
      refreshToken: "refresh",
    });
    const loaded = await loadSession();
    expect(loaded?.accessToken).toBe("access");
    expect(loaded?.appBaseUrl).toBe("http://localhost:5173");
  });
});
