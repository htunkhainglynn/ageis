"use client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type ApiEnvelope<T> = {
  status: string;
  message: string;
  data: T;
};

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  accessToken?: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  let body: ApiEnvelope<T> | { message?: string } | null = null;
  try {
    body = await response.json();
  } catch {
    // A network intermediary can return an empty/non-JSON error response.
  }
  if (!response.ok) {
    throw new ApiError(body?.message ?? "The request could not be completed.", response.status);
  }
  return (body as ApiEnvelope<T>).data;
}
