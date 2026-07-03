/** Inbox / mailbox API endpoints (dev-only automation). */

import type {
  GmailAuthorizeResult,
  MailboxConfig,
  MailboxCredential,
  MailboxTestResult,
  ReplyDraftResult,
} from "../types";
import { request } from "./client";

export const inboxApi = {
  draftReply: (data: {
    classification_id?: number;
    message_uid?: number;
    regenerate?: boolean;
  }) => request<ReplyDraftResult>("/api/v1/inbox/draft-reply", { method: "POST", body: data }),

  listReplyDrafts: (seenJobId?: number) => {
    const query = seenJobId !== undefined ? `?seen_job_id=${seenJobId}` : "";
    return request<ReplyDraftResult[]>(`/api/v1/inbox/reply-drafts${query}`);
  },

  getMailboxCredentials: () => request<MailboxCredential>("/api/v1/inbox/credentials"),

  upsertMailboxCredentials: (data: {
    connector_type?: string;
    enabled?: boolean;
    config: MailboxConfig;
  }) => request<MailboxCredential>("/api/v1/inbox/credentials", { method: "PUT", body: data }),

  deleteMailboxCredentials: () => request<void>("/api/v1/inbox/credentials", { method: "DELETE" }),

  testMailbox: (config?: MailboxConfig) =>
    request<MailboxTestResult>("/api/v1/inbox/test", {
      method: "POST",
      body: config ? { config } : {},
    }),

  gmailAuthorize: () => request<GmailAuthorizeResult>("/api/v1/inbox/gmail/authorize"),
};
