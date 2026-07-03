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

/** Helper: assert the last request() call matches path (+ optional options). */
function lastCall() {
  return request.mock.calls[request.mock.calls.length - 1];
}

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
    expect((requestForm.mock.calls[0][1] as { body: FormData }).body.get("file")).toBe(file);
    await api.deleteResume();
    expect(lastCall()).toEqual(["/api/v1/profile/resume", { method: "DELETE" }]);
    await api.uploadResumeTemplate(file);
    expect(requestForm).toHaveBeenCalledWith(
      "/api/v1/profile/resume-template",
      expect.objectContaining({ method: "PUT", body: expect.any(FormData) }),
    );
    expect((requestForm.mock.calls[1][1] as { body: FormData }).body.get("file")).toBe(file);
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
