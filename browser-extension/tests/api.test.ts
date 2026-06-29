import { afterEach, describe, expect, it, vi } from "vitest";

import { detectSource, login } from "../src/api";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("login", () => {
  it("returns a session with tokens", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({ access_token: "access", refresh_token: "refresh" }),
      })),
    );

    const session = await login(
      "http://localhost:8000/",
      "demo@example.com",
      "secret",
      "http://localhost:5173",
    );
    expect(session.apiBaseUrl).toBe("http://localhost:8000");
    expect(session.appBaseUrl).toBe("http://localhost:5173");
    expect(session.accessToken).toBe("access");
  });
});

describe("detectSource", () => {
  it("posts the active tab URL to the detect endpoint", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({
          adapter_key: "lever",
          suggested_name: "Acme",
          base_url: "https://jobs.lever.co/acme",
          default_config: { site: "acme" },
          query_url: "https://jobs.lever.co/acme",
        }),
    }));
    vi.stubGlobal("fetch", fetchMock);

    const { data } = await detectSource(
      {
        apiBaseUrl: "http://localhost:8000",
        appBaseUrl: "http://localhost:5173",
        accessToken: "token",
        refreshToken: "refresh",
      },
      "https://jobs.lever.co/acme",
      "Acme Careers",
    );

    expect(data.adapter_key).toBe("lever");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/sources/detect",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          url: "https://jobs.lever.co/acme",
          page_title: "Acme Careers",
        }),
      }),
    );
  });
});
