export interface MailboxConfig {
  imap_host: string;
  imap_port?: number;
  imap_use_ssl?: boolean;
  imap_user: string;
  imap_password: string;
  imap_mailbox?: string;
  smtp_host: string;
  smtp_port?: number;
  smtp_use_tls?: boolean;
  smtp_user?: string;
  smtp_password?: string;
  smtp_from?: string;
}

export interface FastmailConfig {
  email_address: string;
  api_token: string;
}

export interface MailboxCredential {
  id: number;
  connector_type: string;
  enabled: boolean;
  created_at: string;
  has_config: boolean;
  imap_host?: string | null;
  smtp_host?: string | null;
  imap_user?: string | null;
  email_address?: string | null;
}

export interface MailboxTestResult {
  imap_ok: boolean;
  smtp_ok: boolean;
  error?: string | null;
}

export interface GmailAuthorizeResult {
  authorization_url: string;
}

/** Mirrors backend `OutlookAuthorizeResponse` (same shape today; kept distinct for drift). */
export interface OutlookAuthorizeResult {
  authorization_url: string;
}

/** Mirrors backend `YahooAuthorizeResponse` (same shape today; kept distinct for drift). */
export interface YahooAuthorizeResult {
  authorization_url: string;
}
