/** Inbox / mailbox API endpoints (dev-only automation). */

import type {
  FastmailConfig,
  GmailAuthorizeResult,
  MailboxConfig,
  MailboxCredential,
  MailboxTestResult,
  ReplyDraftResult,
} from "../types";
import { request } from "./client";

export const inboxApi = {
  draftReply: (data: { classification_id?: number; message_uid?: number; regenerate?: boolean }) =>
    request<ReplyDraftResult>("/api/v1/inbox/draft-reply", { method: "POST", body: data }),

  listReplyDrafts: (seenJobId?: number) => {
    const query = seenJobId !== undefined ? `?seen_job_id=${seenJobId}` : "";
    return request<ReplyDraftResult[]>(`/api/v1/inbox/reply-drafts${query}`);
  },

  getMailboxCredentials: () => request<MailboxCredential>("/api/v1/inbox/credentials"),

  upsertMailboxCredentials: (data: {
    connector_type?: string;
    enabled?: boolean;
    config: MailboxConfig | FastmailConfig;
  }) => request<MailboxCredential>("/api/v1/inbox/credentials", { method: "PUT", body: data }),

  deleteMailboxCredentials: () => request<void>("/api/v1/inbox/credentials", { method: "DELETE" }),

  testMailbox: (data?: { connector_type?: string; config?: MailboxConfig | FastmailConfig }) =>
    request<MailboxTestResult>("/api/v1/inbox/test", {
      method: "POST",
      body: data ?? {},
    }),

  gmailAuthorize: () => request<GmailAuthorizeResult>("/api/v1/inbox/gmail/authorize"),

  outlookAuthorize: () => request<GmailAuthorizeResult>("/api/v1/inbox/outlook/authorize"),

  yahooAuthorize: () => request<GmailAuthorizeResult>("/api/v1/inbox/yahoo/authorize"),
};
