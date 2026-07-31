"use client";

import { createContext, useContext, useMemo, useState } from "react";
import { apiRequest } from "./api";
import type { AuthUser, Role } from "./types";

type Tokens = { access_token: string; refresh_token: string };
type AuthContextValue = {
  user: AuthUser | null;
  accessToken: string | null;
  login(email: string, password: string): Promise<void>;
  logout(): Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function readTokenUser(token: string, fallbackEmail: string): AuthUser {
  try {
    const encoded = token.split(".")[1];
    if (!encoded) throw new Error("Missing JWT payload.");
    const normalized = encoded.replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=")));
    const roleMap: Record<string, Role> = {
      admin: "admin",
      viewer: "viewer",
      api_consumer: "api_consumer",
      "api consumer": "api_consumer",
    };
    const role = roleMap[String(payload.role ?? "").toLowerCase()];
    if (!role) throw new Error("The access token does not contain a supported role.");
    return { email: typeof payload.email === "string" ? payload.email : fallbackEmail, role };
  } catch {
    throw new Error("The server returned an invalid access token.");
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [tokens, setTokens] = useState<Tokens | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    accessToken: tokens?.access_token ?? null,
    async login(email, password) {
      const nextTokens = await apiRequest<Tokens>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      const nextUser = readTokenUser(nextTokens.access_token, email);
      setTokens(nextTokens);
      setUser(nextUser);
    },
    async logout() {
      const accessToken = tokens?.access_token;
      try {
        if (accessToken) {
          await apiRequest("/auth/logout", {
            method: "POST",
            body: JSON.stringify({ access_token: accessToken }),
          }, accessToken);
        }
      } finally {
        setTokens(null);
        setUser(null);
      }
    },
  }), [tokens, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
