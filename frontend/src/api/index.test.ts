import { beforeEach, describe, expect, it, vi } from "vitest";

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
interface RequestOptions {
  method?: Method;
  body?: unknown;
  skipAuth?: boolean;
}

const request = vi.hoisted(() =>
  vi.fn<(path: string, options?: RequestOptions) => Promise<{ ok: true }>>(async () => ({
    ok: true,
  })),
);
const requestBlob = vi.hoisted(() =>
  vi.fn<(path: string) => Promise<Blob>>(async () => new Blob()),
);
const requestForm = vi.hoisted(() =>
  vi.fn<(path: string, options: RequestOptions & { body: FormData }) => Promise<{ ok: true }>>(
    async () => ({ ok: true }),
  ),
);
vi.mock("./client", () => ({ request, requestBlob, requestForm }));

const inboxApi = vi.hoisted(() => ({
  draftReply: vi.fn(),
  listReplyDrafts: vi.fn(),
  getMailboxCredentials: vi.fn(),
  upsertMailboxCredentials: vi.fn(),
  deleteMailboxCredentials: vi.fn(),
  testMailbox: vi.fn(),
  gmailAuthorize: vi.fn(),
  outlookAuthorize: vi.fn(),
  yahooAuthorize: vi.fn(),
}));
vi.mock("./inbox", () => ({ inboxApi }));

import { api } from "./index";

beforeEach(() => {
  request.mockClear();
  requestBlob.mockClear();
  requestForm.mockClear();
});

/** Helper: last request() call as a definite tuple. */
function lastCall(): [string, RequestOptions?] {
  const call = request.mock.calls[request.mock.calls.length - 1];
  if (call === undefined) {
    throw new Error("expected request() to have been called");
  }
  return call as [string, RequestOptions?];
}

describe("api meta + auth", () => {
  it("health skips auth", async () => {
    await api.health();
    expect(request).toHaveBeenCalledWith("/api/v1/health", { skipAuth: true });
  });

  it("meta uses auth", async () => {
    await api.meta();
    expect(request).toHaveBeenCalledWith("/api/v1/meta");
  });

  it("register / login / logout / forgot / reset / verify", async () => {
    await api.register("a@test.io", "pw");
    expect(lastCall()).toEqual([
      "/api/v1/auth/register",
      { method: "POST", body: { email: "a@test.io", password: "pw" }, skipAuth: true },
    ]);
    await api.login("a@test.io", "pw");
    expect(lastCall()[0]).toBe("/api/v1/auth/login");
    await api.logout();
    expect(lastCall()).toEqual(["/api/v1/auth/logout", { method: "POST", skipAuth: true }]);
    await api.forgotPassword("a@test.io");
    expect(lastCall()[1]!.body).toEqual({ email: "a@test.io" });
    await api.resetPassword("tok", "pw");
    expect(lastCall()[1]!.body).toEqual({ token: "tok", password: "pw" });
    await api.verifyEmail("tok");
    expect(lastCall()).toEqual([
      "/api/v1/auth/verify-email",
      { method: "POST", body: { token: "tok" }, skipAuth: true },
    ]);
  });

  it("account / onboarding / export / delete", async () => {
    await api.resendVerificationEmail();
    expect(lastCall()).toEqual(["/api/v1/auth/resend-verification", { method: "POST" }]);
    await api.me();
    expect(lastCall()[0]).toBe("/api/v1/auth/me");
    await api.completeOnboarding();
    expect(lastCall()).toEqual(["/api/v1/auth/me/complete-onboarding", { method: "POST" }]);
    await api.exportMyData();
    expect(lastCall()[0]).toBe("/api/v1/auth/me/export");
    await api.deleteAccount("pw");
    expect(lastCall()).toEqual(["/api/v1/auth/me", { method: "DELETE", body: { password: "pw" } }]);
  });
});

describe("api billing", () => {
  it("status + validate promo", async () => {
    await api.billingStatus();
    expect(lastCall()[0]).toBe("/api/v1/billing/status");
    await api.validatePromoCode("SAVE20");
    expect(lastCall()[1]!.body).toEqual({ code: "SAVE20" });
  });

  it("checkout uses defaults", async () => {
    await api.createCheckout();
    expect(lastCall()[1]!.body).toEqual({ plan: "pro", billing_period: "monthly" });
  });

  it("checkout includes an explicit plan, period and promo code", async () => {
    await api.createCheckout("plus", "annual", "PROMO");
    expect(lastCall()[1]!.body).toEqual({
      plan: "plus",
      billing_period: "annual",
      promo_code: "PROMO",
    });
  });

  it("opens the billing portal", async () => {
    await api.createBillingPortal();
    expect(lastCall()).toEqual(["/api/v1/billing/portal", { method: "POST", body: {} }]);
  });
});

describe("api admin", () => {
  it("users + stats", async () => {
    await api.listAdminUsers();
    expect(lastCall()[0]).toBe("/api/v1/admin/users");
    await api.updateAdminUser(5, { is_active: false });
    expect(lastCall()).toEqual([
      "/api/v1/admin/users/5",
      { method: "PATCH", body: { is_active: false } },
    ]);
    await api.getAdminStats();
    expect(lastCall()[0]).toBe("/api/v1/admin/stats");
  });

  it("data requests default and custom limit", async () => {
    await api.listAdminDataRequests();
    expect(lastCall()[0]).toBe("/api/v1/admin/data-requests?limit=100");
    await api.listAdminDataRequests(5);
    expect(lastCall()[0]).toBe("/api/v1/admin/data-requests?limit=5");
  });

  it("promo codes CRUD", async () => {
    await api.listAdminPromoCodes();
    expect(lastCall()[0]).toBe("/api/v1/admin/promo-codes");
    await api.createAdminPromoCode({ code: "X", promo_type: "percent_off", value_int: 20 });
    expect(lastCall()[0]).toBe("/api/v1/admin/promo-codes");
    await api.updateAdminPromoCode(3, { active: false });
    expect(lastCall()).toEqual([
      "/api/v1/admin/promo-codes/3",
      { method: "PATCH", body: { active: false } },
    ]);
    await api.listAdminPromoRedemptions(3);
    expect(lastCall()[0]).toBe("/api/v1/admin/promo-codes/3/redemptions");
  });
});

describe("api portals + sources", () => {
  it("lists portals with and without filters", async () => {
    await api.listPortals();
    expect(lastCall()[0]).toBe("/api/v1/portals");
    await api.listPortals({ category: "tech", q: "acme" });
    expect(lastCall()[0]).toBe("/api/v1/portals?category=tech&q=acme");
  });

  it("searches and subscribes to portals", async () => {
    await api.searchPortals({} as never);
    expect(lastCall()[0]).toBe("/api/v1/portals/search");
    await api.subscribePortals({} as never);
    expect(lastCall()[0]).toBe("/api/v1/portals/subscribe");
  });

  it("sources CRUD + detect + test", async () => {
    await api.listSources();
    expect(lastCall()[0]).toBe("/api/v1/sources");
    await api.detectSource("https://x.test");
    expect(lastCall()[1]!.body).toEqual({ url: "https://x.test", page_title: null });
    await api.detectSource("https://x.test", "Careers");
    expect(lastCall()[1]!.body).toEqual({ url: "https://x.test", page_title: "Careers" });
    await api.createSource({} as never);
    expect(lastCall()[0]).toBe("/api/v1/sources");
    await api.updateSource(2, {});
    expect(lastCall()[0]).toBe("/api/v1/sources/2");
    await api.deleteSource(2);
    expect(lastCall()).toEqual(["/api/v1/sources/2", { method: "DELETE" }]);
    await api.testSource(2);
    expect(lastCall()[0]).toBe("/api/v1/sources/2/test");
  });
});

describe("api searches", () => {
  it("CRUD + run", async () => {
    await api.listSearches();
    expect(lastCall()[0]).toBe("/api/v1/searches");
    await api.createSearch({} as never);
    expect(lastCall()[0]).toBe("/api/v1/searches");
    await api.updateSearch(9, {});
    expect(lastCall()[0]).toBe("/api/v1/searches/9");
    await api.deleteSearch(9);
    expect(lastCall()).toEqual(["/api/v1/searches/9", { method: "DELETE" }]);
    await api.runSearch(9);
    expect(lastCall()).toEqual(["/api/v1/searches/9/run", { method: "POST" }]);
    await api.getSearchRun(9);
    expect(lastCall()[0]).toBe("/api/v1/search-runs/9");
  });
});

describe("api jobs", () => {
  it("lists jobs with every query combination", async () => {
    await api.listJobs();
    expect(lastCall()[0]).toBe("/api/v1/jobs");
    await api.listJobs(3);
    expect(lastCall()[0]).toBe("/api/v1/jobs?search_id=3");
    await api.listJobs(undefined, "new");
    expect(lastCall()[0]).toBe("/api/v1/jobs?status=new");
    await api.listJobs(3, "applied");
    expect(lastCall()[0]).toBe("/api/v1/jobs?search_id=3&status=applied");
  });

  it("updates, applies, and generates", async () => {
    await api.updateJob(1, { status: "applied" });
    expect(lastCall()[0]).toBe("/api/v1/jobs/1");
    await api.applyToJob(1, { dry_run: true });
    expect(lastCall()[0]).toBe("/api/v1/jobs/1/apply");
    await api.generateCoverLetter(1);
    expect(lastCall()[0]).toBe("/api/v1/jobs/1/generate-cover-letter");
    await api.generateResume(1);
    expect(lastCall()[0]).toBe("/api/v1/jobs/1/generate-resume");
    await api.getDocumentGeneration(9);
    expect(lastCall()[0]).toBe("/api/v1/document-generations/9");
  });
});

describe("api application logs + pipeline", () => {
  it("lists logs with default and custom limit", async () => {
    await api.listApplicationLogs();
    expect(lastCall()[0]).toBe("/api/v1/application-logs?limit=100");
    await api.listApplicationLogs(10);
    expect(lastCall()[0]).toBe("/api/v1/application-logs?limit=10");
  });

  it("gets a log and downloads an artifact", async () => {
    await api.getApplicationLog(4);
    expect(lastCall()[0]).toBe("/api/v1/application-logs/4");
    await api.downloadApplicationArtifact(4);
    expect(requestBlob).toHaveBeenCalledWith("/api/v1/application-artifacts/4/download");
  });

  it("lists applications with and without a stage filter", async () => {
    await api.listApplications();
    expect(lastCall()[0]).toBe("/api/v1/applications");
    await api.listApplications("awaiting_reply");
    expect(lastCall()[0]).toBe("/api/v1/applications?stage=awaiting_reply");
  });
});

describe("api inbox delegation", () => {
  it("wires each inbox method through to inboxApi", () => {
    expect(api.draftInboxReply).toBe(inboxApi.draftReply);
    expect(api.listInboxReplyDrafts).toBe(inboxApi.listReplyDrafts);
    expect(api.getMailboxCredentials).toBe(inboxApi.getMailboxCredentials);
    expect(api.upsertMailboxCredentials).toBe(inboxApi.upsertMailboxCredentials);
    expect(api.deleteMailboxCredentials).toBe(inboxApi.deleteMailboxCredentials);
    expect(api.testMailbox).toBe(inboxApi.testMailbox);
    expect(api.gmailAuthorize).toBe(inboxApi.gmailAuthorize);
    expect(api.outlookAuthorize).toBe(inboxApi.outlookAuthorize);
    expect(api.yahooAuthorize).toBe(inboxApi.yahooAuthorize);
  });
});

describe("api feed + targets + credentials", () => {
  it("feed url + rotate", async () => {
    await api.getFeedUrl();
    expect(lastCall()[0]).toBe("/api/v1/feed/url");
    await api.rotateFeedUrl();
    expect(lastCall()).toEqual(["/api/v1/feed/rotate", { method: "POST" }]);
  });

  it("targets CRUD + test", async () => {
    await api.listTargets();
    expect(lastCall()[0]).toBe("/api/v1/targets");
    await api.createTarget({} as never);
    expect(lastCall()[0]).toBe("/api/v1/targets");
    await api.updateTarget(6, {});
    expect(lastCall()[0]).toBe("/api/v1/targets/6");
    await api.deleteTarget(6);
    expect(lastCall()).toEqual(["/api/v1/targets/6", { method: "DELETE" }]);
    await api.testTarget(6);
    expect(lastCall()).toEqual(["/api/v1/targets/6/test", { method: "POST" }]);
  });

  it("credentials CRUD", async () => {
    await api.listCredentials();
    expect(lastCall()[0]).toBe("/api/v1/credentials");
    await api.createCredential({} as never);
    expect(lastCall()[0]).toBe("/api/v1/credentials");
    await api.updateCredential(8, {});
    expect(lastCall()[0]).toBe("/api/v1/credentials/8");
    await api.deleteCredential(8);
    expect(lastCall()).toEqual(["/api/v1/credentials/8", { method: "DELETE" }]);
  });
});

describe("api profile", () => {
  it("get + save + delete", async () => {
    await api.getProfile();
    expect(lastCall()[0]).toBe("/api/v1/profile");
    await api.saveProfile({} as never);
    expect(lastCall()).toEqual(["/api/v1/profile", { method: "PUT", body: {} }]);
    await api.deleteProfile();
    expect(lastCall()).toEqual(["/api/v1/profile", { method: "DELETE" }]);
  });

  it("uploads and deletes resume + template through requestForm", async () => {
    const file = new File(["x"], "resume.pdf");
    await api.uploadResume(file);
    expect(requestForm).toHaveBeenCalledWith(
      "/api/v1/profile/resume",
      expect.objectContaining({ method: "PUT", body: expect.any(FormData) }),
    );
    expect((requestForm.mock.calls[0]![1] as { body: FormData }).body.get("file")).toBe(file);
    await api.deleteResume();
    expect(lastCall()).toEqual(["/api/v1/profile/resume", { method: "DELETE" }]);
    await api.uploadResumeTemplate(file);
    expect(requestForm).toHaveBeenCalledWith(
      "/api/v1/profile/resume-template",
      expect.objectContaining({ method: "PUT", body: expect.any(FormData) }),
    );
    expect((requestForm.mock.calls[1]![1] as { body: FormData }).body.get("file")).toBe(file);
    await api.deleteResumeTemplate();
    expect(lastCall()).toEqual(["/api/v1/profile/resume-template", { method: "DELETE" }]);
  });
});

describe("api summary preferences", () => {
  it("get + update", async () => {
    await api.getSummaryPreferences();
    expect(lastCall()[0]).toBe("/api/v1/summary-preferences");
    await api.updateSummaryPreferences({} as never);
    expect(lastCall()).toEqual(["/api/v1/summary-preferences", { method: "PATCH", body: {} }]);
  });
});
