import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  refreshSession,
  request,
  requestBlob,
  requestForm,
  setUnauthorizedHandler,
} from "./client";

const settings = vi.hoisted(() => ({
  accessToken: "access-1",
  base: "http://api.test",
  cleared: false,
}));

vi.mock("../lib/settings", () => ({
  getApiBaseUrl: () => settings.base,
  getAccessToken: () => settings.accessToken,
  setAccessToken: vi.fn((token: string) => {
    settings.accessToken = token;
  }),
  clearAccessToken: vi.fn(() => {
    settings.cleared = true;
    settings.accessToken = "";
  }),
}));

function jsonResponse(status: number, body: unknown, statusText = ""): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    statusText,
    json: async () => body,
    text: async () => (body === undefined ? "" : JSON.stringify(body)),
    blob: async () => new Blob([JSON.stringify(body)]),
  } as unknown as Response;
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  settings.accessToken = "access-1";
  settings.cleared = false;
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  setUnauthorizedHandler(null);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

type FetchInit = {
  method?: string;
  body?: unknown;
  credentials?: string;
  headers: Record<string, string>;
};

/** First (or nth) fetch call args as a definite tuple. */
function fetchCall(index = 0): [unknown, FetchInit] {
  const call = fetchMock.mock.calls[index];
  if (call === undefined) {
    throw new Error(`expected fetch to have been called (index ${index})`);
  }
  return call as [unknown, FetchInit];
}

describe("ApiError", () => {
  it("carries status and name", () => {
    const err = new ApiError(404, "nope");
    expect(err.status).toBe(404);
    expect(err.name).toBe("ApiError");
    expect(err.message).toBe("nope");
  });
});

describe("request", () => {
  it("sends the bearer token and JSON body on a normal request", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    const data = await request<{ ok: boolean }>("/thing", { method: "POST", body: { a: 1 } });
    expect(data).toEqual({ ok: true });
    const [url, init] = fetchCall();
    expect(url).toBe("http://api.test/thing");
    expect(init.method).toBe("POST");
    expect(init.headers["Authorization"]).toBe("Bearer access-1");
    expect(init.body).toBe(JSON.stringify({ a: 1 }));
    expect(init.credentials).toBe("include");
  });

  it("omits the body when undefined", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, {}));
    await request("/thing");
    expect(fetchCall(0)[1].body).toBeUndefined();
  });

  it("skips auth for public endpoints (no Authorization header)", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, {}));
    await request("/public", { skipAuth: true });
    expect(fetchCall(0)[1].headers["Authorization"]).toBeUndefined();
  });

  it("returns undefined on 204", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(204, undefined));
    expect(await request("/thing")).toBeUndefined();
  });

  it("parses an empty body as undefined", async () => {
    fetchMock.mockResolvedValueOnce({
      status: 200,
      ok: true,
      statusText: "OK",
      text: async () => "",
    } as unknown as Response);
    expect(await request("/thing")).toBeUndefined();
  });

  it("throws ApiError with the detail message on failure", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(400, { detail: "bad" }, "Bad Request"));
    await expect(request("/thing")).rejects.toMatchObject({ status: 400, message: "bad" });
  });

  it("falls back to statusText when no detail is present", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(500, {}, "Server Error"));
    await expect(request("/thing")).rejects.toMatchObject({ message: "Server Error" });
  });

  it("throws ApiError instead of SyntaxError on malformed JSON 2xx body", async () => {
    fetchMock.mockResolvedValueOnce({
      status: 200,
      ok: true,
      statusText: "OK",
      text: async () => "<html>gateway</html>",
    } as unknown as Response);
    await expect(request("/thing")).rejects.toMatchObject({
      name: "ApiError",
      status: 200,
      message: "<html>gateway</html>",
    });
  });

  it("throws ApiError on malformed JSON error bodies for requestForm too", async () => {
    const body = new FormData();
    fetchMock.mockResolvedValueOnce({
      status: 502,
      ok: false,
      statusText: "Bad Gateway",
      text: async () => "<html>bad gateway</html>",
    } as unknown as Response);
    await expect(requestForm("/upload", { body })).rejects.toMatchObject({
      name: "ApiError",
      status: 502,
      message: "<html>bad gateway</html>",
    });
  });

  it("refreshes once on 401 then retries with the new token", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
      .mockResolvedValueOnce(jsonResponse(200, { access_token: "access-2" }))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    const data = await request<{ ok: boolean }>("/thing");
    expect(data).toEqual({ ok: true });
    expect(fetchCall(2)[1].headers["Authorization"]).toBe("Bearer access-2");
  });

  it("clears the session and notifies the handler when refresh fails", async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
      .mockResolvedValueOnce(jsonResponse(401, {}));
    await expect(request("/thing")).rejects.toMatchObject({ status: 401 });
    expect(settings.cleared).toBe(true);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("clears the session when the retry after a successful refresh is still 401", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, {}))
      .mockResolvedValueOnce(jsonResponse(200, { access_token: "access-2" }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: "still bad" }));
    await expect(request("/thing")).rejects.toMatchObject({ status: 401 });
    expect(settings.cleared).toBe(true);
  });

  it("shares one refresh across concurrent 401s from request helpers", async () => {
    let resolveRefresh: ((value: Response) => void) | undefined;
    const refreshPending = new Promise<Response>((resolve) => {
      resolveRefresh = resolve;
    });
    const body = new FormData();
    let phase: "expire" | "ok" = "expire";
    fetchMock.mockImplementation((url: string) => {
      if (String(url).endsWith("/api/v1/auth/refresh")) return refreshPending;
      if (phase === "expire") {
        return Promise.resolve(jsonResponse(401, { detail: "expired" }));
      }
      return Promise.resolve(jsonResponse(200, { ok: true }));
    });

    const pending = Promise.all([
      request<{ ok: boolean }>("/a"),
      requestForm<{ ok: boolean }>("/b", { body }),
      requestBlob("/c").then(() => ({ ok: true })),
    ]);
    await vi.waitFor(() => {
      expect(
        fetchMock.mock.calls.filter(([u]) => String(u).endsWith("/api/v1/auth/refresh")),
      ).toHaveLength(1);
    });

    phase = "ok";
    resolveRefresh!(jsonResponse(200, { access_token: "access-2" }));
    expect(await pending).toEqual([{ ok: true }, { ok: true }, { ok: true }]);
    expect(
      fetchMock.mock.calls.filter(([u]) => String(u).endsWith("/api/v1/auth/refresh")),
    ).toHaveLength(1);
  });
});

describe("refreshSession", () => {
  it("stores the new token on success", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { access_token: "fresh" }));
    expect(await refreshSession()).toBe(true);
    expect(settings.accessToken).toBe("fresh");
  });

  it("returns false when the refresh endpoint rejects", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(401, {}));
    expect(await refreshSession()).toBe(false);
  });

  it("returns false on network failure instead of throwing", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    expect(await refreshSession()).toBe(false);
    expect(settings.accessToken).toBe("access-1");
  });

  it("returns false when a 2xx refresh body is not JSON", async () => {
    fetchMock.mockResolvedValueOnce({
      status: 200,
      ok: true,
      statusText: "OK",
      json: async () => {
        throw new SyntaxError("Unexpected token <");
      },
    } as unknown as Response);
    expect(await refreshSession()).toBe(false);
    expect(settings.accessToken).toBe("access-1");
  });

  it("clears the session when a 401 refresh fails with a network error", async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(request("/thing")).rejects.toMatchObject({ status: 401 });
    expect(settings.cleared).toBe(true);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("dedupes concurrent callers onto one POST /auth/refresh", async () => {
    let resolveRefresh: ((value: Response) => void) | undefined;
    const refreshPending = new Promise<Response>((resolve) => {
      resolveRefresh = resolve;
    });
    fetchMock.mockImplementationOnce(() => refreshPending);

    const first = refreshSession();
    const second = refreshSession();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchCall(0)[0]).toBe("http://api.test/api/v1/auth/refresh");

    resolveRefresh!(jsonResponse(200, { access_token: "shared" }));
    expect(await Promise.all([first, second])).toEqual([true, true]);
    expect(settings.accessToken).toBe("shared");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("allows a new refresh after the previous in-flight one settles", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, { access_token: "first" }))
      .mockResolvedValueOnce(jsonResponse(200, { access_token: "second" }));
    expect(await refreshSession()).toBe(true);
    expect(await refreshSession()).toBe(true);
    expect(settings.accessToken).toBe("second");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe("requestForm", () => {
  const body = new FormData();

  it("posts multipart with the bearer token and no Content-Type", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    await requestForm("/upload", { body });
    const init = fetchCall(0)[1];
    expect(init.method).toBe("POST");
    expect(init.headers["Authorization"]).toBe("Bearer access-1");
    expect(init.headers["Content-Type"]).toBeUndefined();
    expect(init.body).toBe(body);
  });

  it("skips auth when requested", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, {}));
    await requestForm("/upload", { body, skipAuth: true });
    expect(fetchCall(0)[1].headers["Authorization"]).toBeUndefined();
  });

  it("uses an explicit method override", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, {}));
    await requestForm("/upload", { body, method: "PUT" });
    expect(fetchCall(0)[1].method).toBe("PUT");
  });

  it("refreshes on 401 and retries", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, {}))
      .mockResolvedValueOnce(jsonResponse(200, { access_token: "access-2" }))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    expect(await requestForm("/upload", { body })).toEqual({ ok: true });
  });

  it("clears the session when refresh fails", async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, {}))
      .mockResolvedValueOnce(jsonResponse(401, {}));
    await expect(requestForm("/upload", { body })).rejects.toMatchObject({ status: 401 });
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });
});

describe("requestBlob", () => {
  it("downloads the blob with the bearer token", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { pdf: true }));
    const blob = await requestBlob("/artifacts/1/download");
    expect(blob).toBeInstanceOf(Blob);
    expect(fetchCall(0)[1].headers["Authorization"]).toBe("Bearer access-1");
  });

  it("omits the Authorization header when no token is held", async () => {
    settings.accessToken = "";
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { pdf: true }));
    expect(await requestBlob("/artifacts/1/download")).toBeInstanceOf(Blob);
    expect(fetchCall(0)[1].headers["Authorization"]).toBeUndefined();
  });

  it("refreshes on 401 and retries", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, {}))
      .mockResolvedValueOnce(jsonResponse(200, { access_token: "access-2" }))
      .mockResolvedValueOnce(jsonResponse(200, { pdf: true }));
    expect(await requestBlob("/artifacts/1/download")).toBeInstanceOf(Blob);
  });

  it("clears the session when refresh fails", async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, {}))
      .mockResolvedValueOnce(jsonResponse(401, {}));
    await expect(requestBlob("/artifacts/1/download")).rejects.toMatchObject({ status: 401 });
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("throws ApiError with the JSON detail on non-ok responses", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(404, { detail: "missing" }, "Not Found"));
    await expect(requestBlob("/artifacts/1/download")).rejects.toMatchObject({
      status: 404,
      message: "missing",
    });
  });

  it("falls back to statusText when the error body has no detail", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(500, {}, "Boom"));
    await expect(requestBlob("/artifacts/1/download")).rejects.toMatchObject({ message: "Boom" });
  });

  it("uses the raw text when the error body is not JSON", async () => {
    fetchMock.mockResolvedValueOnce({
      status: 502,
      ok: false,
      statusText: "Bad Gateway",
      text: async () => "gateway down",
      blob: async () => new Blob(),
    } as unknown as Response);
    await expect(requestBlob("/artifacts/1/download")).rejects.toMatchObject({
      message: "gateway down",
    });
  });

  it("falls back to statusText when the error body is empty and unparseable", async () => {
    fetchMock.mockResolvedValueOnce({
      status: 503,
      ok: false,
      statusText: "Unavailable",
      text: async () => "",
      blob: async () => new Blob(),
    } as unknown as Response);
    await expect(requestBlob("/artifacts/1/download")).rejects.toMatchObject({
      message: "Unavailable",
    });
  });
});
