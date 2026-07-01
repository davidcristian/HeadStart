export interface SiteCredential {
  id: number;
  source_id: number;
  name: string;
  enabled: boolean;
  created_at: string;
  has_cookies: boolean;
  has_headers: boolean;
  has_session: boolean;
}

export interface CredentialCreate {
  source_id: number;
  name: string;
  enabled: boolean;
  cookies: Record<string, string>;
  headers: Record<string, string>;
  session: Record<string, string>;
}

export interface CredentialExport {
  id: number;
  source_id: number;
  name: string;
  enabled: boolean;
  created_at: string;
  cookies: Record<string, string>;
  headers: Record<string, string>;
  session: Record<string, string>;
}
