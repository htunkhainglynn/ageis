export type Role = "admin" | "viewer" | "api_consumer";

export type AuthUser = {
  email: string;
  role: Role;
};

export type UserItem = {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  role: Role;
  created_at: string;
  updated_at: string;
};

export type ApiKeyItem = {
  id: number;
  name: string;
  key_prefix: string;
  owner_id: number;
  scopes: string[];
  status: "active" | "revoked";
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
};

export type RateLimitRule = {
  id: number;
  name: string;
  scope_type: "global" | "api_key" | "route";
  scope_value: string | null;
  algorithm: "token_bucket" | "sliding_window" | "fixed_window";
  limit_count: number;
  window_seconds: number;
  burst_allowance: number | null;
  status: "active" | "disabled";
  created_at: string;
};

export type JwtConfig = {
  id: number;
  name: string;
  algorithm: "HS256" | "RS256" | "ES256";
  signing_key_masked: string;
  public_key_masked: string | null;
  issuer: string | null;
  audience: string | null;
  access_token_ttl_seconds: number;
  refresh_token_ttl_seconds: number;
  status: "active" | "disabled";
  created_at: string;
};
