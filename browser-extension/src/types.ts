/** Types mirroring backend schemas used by the extension. */

export interface SourceDetectResult {
  adapter_key: string;
  suggested_name: string;
  base_url: string;
  default_config: Record<string, unknown>;
  query_url: string;
}

export interface Source {
  id: number;
  name: string;
  adapter_key: string;
  base_url: string;
  default_config: Record<string, unknown>;
  enabled: boolean;
}

export interface Search {
  id: number;
  name: string;
  source_id: number;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
}

export interface Session {
  apiBaseUrl: string;
  appBaseUrl: string;
  accessToken: string;
  refreshToken: string;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
