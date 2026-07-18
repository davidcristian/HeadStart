/** Inbox / mailbox API endpoints (dev-only automation). */

import type {
  FastmailConfig,
  GmailAuthorizeResult,
  MailboxConfig,
  MailboxCredential,
  MailboxTestResult,
  OutlookAuthorizeResult,
  ReplyDraftResult,
  YahooAuthorizeResult,
} from "../types";
import { request } from "./client";

function replyDraftsQuery(seenJobId?: number, limit?: number): string {
  const params = new URLSearchParams();
  if (seenJobId !== undefined) params.set("seen_job_id", String(seenJobId));
  if (limit !== undefined) params.set("limit", String(limit));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export const inboxApi = {
  draftReply: (data: { classification_id?: number; message_uid?: number; regenerate?: boolean }) =>
    request<ReplyDraftResult>("/api/v1/inbox/draft-reply", { method: "POST", body: data }),

  listReplyDrafts: (seenJobId?: number, limit?: number) =>
    request<ReplyDraftResult[]>(`/api/v1/inbox/reply-drafts${replyDraftsQuery(seenJobId, limit)}`),

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

  outlookAuthorize: () => request<OutlookAuthorizeResult>("/api/v1/inbox/outlook/authorize"),

  yahooAuthorize: () => request<YahooAuthorizeResult>("/api/v1/inbox/yahoo/authorize"),
};
