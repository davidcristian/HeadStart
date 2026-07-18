import { beforeEach, describe, expect, it, vi } from "vitest";

const request = vi.hoisted(() => vi.fn(async () => ({ ok: true })));
vi.mock("./client", () => ({ request }));

import { inboxApi } from "./inbox";

beforeEach(() => {
  request.mockClear();
});

describe("inboxApi", () => {
  it("drafts a reply", async () => {
    await inboxApi.draftReply({ classification_id: 7, regenerate: true });
    expect(request).toHaveBeenCalledWith("/api/v1/inbox/draft-reply", {
      method: "POST",
      body: { classification_id: 7, regenerate: true },
    });
  });

  it("lists reply drafts scoped to a job", async () => {
    await inboxApi.listReplyDrafts(42);
    expect(request).toHaveBeenCalledWith("/api/v1/inbox/reply-drafts?seen_job_id=42");
  });

  it("lists reply drafts with a limit", async () => {
    await inboxApi.listReplyDrafts(undefined, 25);
    expect(request).toHaveBeenCalledWith("/api/v1/inbox/reply-drafts?limit=25");
  });

  it("lists reply drafts with job id and limit", async () => {
    await inboxApi.listReplyDrafts(7, 10);
    expect(request).toHaveBeenCalledWith("/api/v1/inbox/reply-drafts?seen_job_id=7&limit=10");
  });

  it("lists all reply drafts when no job id is given", async () => {
    await inboxApi.listReplyDrafts();
    expect(request).toHaveBeenCalledWith("/api/v1/inbox/reply-drafts");
  });

  it("gets mailbox credentials", async () => {
    await inboxApi.getMailboxCredentials();
    expect(request).toHaveBeenCalledWith("/api/v1/inbox/credentials");
  });

  it("upserts mailbox credentials", async () => {
    const config = { host: "imap.test" } as never;
    await inboxApi.upsertMailboxCredentials({ enabled: true, config });
    expect(request).toHaveBeenCalledWith("/api/v1/inbox/credentials", {
      method: "PUT",
      body: { enabled: true, config },
    });
  });

  it("deletes mailbox credentials", async () => {
    await inboxApi.deleteMailboxCredentials();
    expect(request).toHaveBeenCalledWith("/api/v1/inbox/credentials", { method: "DELETE" });
  });

  it("tests the mailbox with the provided data", async () => {
    const config = { host: "imap.test" } as never;
    await inboxApi.testMailbox({ connector_type: "imap_smtp", config });
    expect(request).toHaveBeenCalledWith("/api/v1/inbox/test", {
      method: "POST",
      body: { connector_type: "imap_smtp", config },
    });
  });

  it("tests the mailbox with an empty body when no data is given", async () => {
    await inboxApi.testMailbox();
    expect(request).toHaveBeenCalledWith("/api/v1/inbox/test", { method: "POST", body: {} });
  });

  it("authorizes gmail, outlook and yahoo", async () => {
    await inboxApi.gmailAuthorize();
    await inboxApi.outlookAuthorize();
    await inboxApi.yahooAuthorize();
    expect(request).toHaveBeenCalledWith("/api/v1/inbox/gmail/authorize");
    expect(request).toHaveBeenCalledWith("/api/v1/inbox/outlook/authorize");
    expect(request).toHaveBeenCalledWith("/api/v1/inbox/yahoo/authorize");
  });
});
